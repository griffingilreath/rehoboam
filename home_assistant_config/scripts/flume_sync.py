#!/usr/bin/env python3
"""
flume_sync.py — Fetch yesterday's categorized water usage from the Flume portal.

Flume's AI categorization (shower, toilet, etc.) is only available after midnight
when their servers process the prior day's data. Run this at 02:00 AM daily.

Schedule via HA automation + shell_command:
  shell_command:
    flume_sync: >-
      python3 /config/scripts/flume_sync.py
      --output /config/flume_categories.json
      --token-cache /config/.flume_token_cache.json
      >> /config/logs/flume_sync.log 2>&1

Credentials — set as environment variables or in secrets.yaml and pass as args:
  FLUME_CLIENT_ID, FLUME_CLIENT_SECRET, FLUME_USERNAME, FLUME_PASSWORD

Usage:
  python3 flume_sync.py [OPTIONS]

Options:
  --output PATH          Where to write the JSON output  [required]
  --date DATE            Target date YYYY-MM-DD (default: yesterday)
  --token-cache PATH     Cache file for auth token (avoids re-login each run)
  --client-id ID         Flume OAuth client ID
  --client-secret SECRET Flume OAuth client secret
  --username EMAIL       Flume account email
  --password PASSWORD    Flume account password
  --verbose              Print debug output

Exit codes:
  0 — success
  1 — auth failure (check credentials)
  2 — API error (Flume may be down, retry later)
  3 — no device found
  4 — bad arguments
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(4)

# ─── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://api.flumetech.com"

# Flume category IDs → human-readable names
CATEGORIES = {
    1: "shower",
    2: "toilet",
    3: "faucet",
    4: "irrigation",
    5: "bathtub",
    6: "laundry",
    7: "dishwasher",
    8: "other",
    9: "leak",
}

log = logging.getLogger("flume_sync")


# ─── Auth ─────────────────────────────────────────────────────────────────────

def load_cached_token(cache_path: Path) -> dict | None:
    """Load a previously cached token if it's still valid (with 5-min buffer)."""
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text())
        expires_at = data.get("expires_at", 0)
        if time.time() < expires_at - 300:   # 5-minute buffer before expiry
            log.debug("Using cached token (expires in %.0f min)", (expires_at - time.time()) / 60)
            return data
        log.debug("Cached token expired, will re-authenticate")
    except Exception as exc:
        log.warning("Could not read token cache: %s", exc)
    return None


def save_cached_token(cache_path: Path, token_data: dict) -> None:
    """Save token to cache file with an expiry timestamp."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(token_data, indent=2))
        cache_path.chmod(0o600)   # Restrict to owner only
    except Exception as exc:
        log.warning("Could not save token cache: %s", exc)


def get_token(args, cache_path: Path | None) -> str:
    """Return a valid Bearer token, using cache if available."""
    if cache_path:
        cached = load_cached_token(cache_path)
        if cached:
            return cached["access_token"]

    log.info("Authenticating with Flume API...")
    try:
        resp = requests.post(
            f"{BASE_URL}/oauth/token",
            json={
                "grant_type": "password",
                "client_id": args.client_id,
                "client_secret": args.client_secret,
                "username": args.username,
                "password": args.password,
            },
            timeout=30,
        )
        if resp.status_code == 401:
            log.error("Authentication failed — check client ID, secret, username, and password")
            sys.exit(1)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Network error during authentication: %s", exc)
        sys.exit(2)

    body = resp.json()
    # Flume wraps everything in a "data" array
    token_obj = body["data"][0] if isinstance(body.get("data"), list) else body
    access_token = token_obj["access_token"]
    expires_in = int(token_obj.get("expires_in", 3600))

    if cache_path:
        save_cached_token(cache_path, {
            "access_token": access_token,
            "expires_at": time.time() + expires_in,
            "token_type": token_obj.get("token_type", "Bearer"),
        })

    log.info("Authentication successful (token valid for %d min)", expires_in // 60)
    return access_token


# ─── API helpers ──────────────────────────────────────────────────────────────

def api_get(token: str, path: str, params: dict | None = None) -> dict:
    """GET from the Flume API with error handling."""
    try:
        resp = requests.get(
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        log.error("API GET %s failed: %s", path, exc)
        sys.exit(2)


def api_post(token: str, path: str, payload: dict) -> dict:
    """POST to the Flume API with error handling."""
    try:
        resp = requests.post(
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        log.error("API POST %s failed: %s", path, exc)
        sys.exit(2)


def get_user_id(token: str) -> str:
    """Get the authenticated user's ID."""
    body = api_get(token, "/me")
    user_id = body["data"][0]["id"]
    log.debug("User ID: %s", user_id)
    return user_id


def get_device_id(token: str, user_id: str) -> str:
    """Find the first Flume 2 water monitor device."""
    body = api_get(token, f"/me/devices", params={
        "user_id": user_id,
        "location": "true",
        "list_shared": "true",
    })
    for device in body.get("data", []):
        if device.get("type") == 2:   # Type 2 = Flume 2 Smart Water Sensor
            log.info("Found device: %s (location: %s)", device["id"],
                     device.get("location", {}).get("name", "unknown"))
            return device["id"]
    log.error("No Flume water monitor device found in your account")
    sys.exit(3)


# ─── Category query ───────────────────────────────────────────────────────────

def fetch_categories(token: str, user_id: str, device_id: str, target_date: date) -> dict:
    """
    Query Flume for each usage category on a specific date.

    Returns a dict: {"shower": 12.5, "toilet": 8.3, ...}
    """
    since = f"{target_date} 00:00:00"
    until = f"{target_date} 23:59:59"

    # Build one sub-query per category
    queries = [
        {
            "request_id": name,
            "bucket": "DAY",
            "since_datetime": since,
            "until_datetime": until,
            "operation": "SUM",
            "units": "GALLONS",
            "category": cat_id,
        }
        for cat_id, name in CATEGORIES.items()
    ]

    log.info("Querying %d categories for %s...", len(queries), target_date)
    body = api_post(token, f"/me/users/{user_id}/devices/{device_id}/query",
                    {"queries": queries})

    results: dict[str, float] = {name: 0.0 for name in CATEGORIES.values()}

    for item in body.get("data", []):
        cat_name = item.get("request_id")
        if cat_name not in results:
            continue
        values = item.get("value") or []
        total = sum(float(v.get("value", 0)) for v in values if v.get("value") is not None)
        results[cat_name] = round(total, 3)

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

def build_output(target_date: date, categories: dict, device_id: str) -> dict:
    total = round(sum(categories.values()), 3)
    return {
        "date": target_date.isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "device_id": device_id,
        "total_gallons": total,
        "categories": categories,
        "status": "success",
    }


def write_output(path: Path, data: dict) -> None:
    # Atomic write: write to .tmp then rename to avoid partial reads
    tmp = path.with_suffix(".json.tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path)
    log.info("Wrote output to %s", path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--output", required=True, type=Path,
                        help="Path to write the JSON output file")
    parser.add_argument("--date", type=date.fromisoformat,
                        default=date.today() - timedelta(days=1),
                        help="Date to fetch (YYYY-MM-DD, default: yesterday)")
    parser.add_argument("--token-cache", type=Path,
                        help="Path to cache the auth token between runs")
    parser.add_argument("--client-id",
                        default=os.environ.get("FLUME_CLIENT_ID"),
                        help="Flume OAuth client ID [env: FLUME_CLIENT_ID]")
    parser.add_argument("--client-secret",
                        default=os.environ.get("FLUME_CLIENT_SECRET"),
                        help="Flume OAuth client secret [env: FLUME_CLIENT_SECRET]")
    parser.add_argument("--username",
                        default=os.environ.get("FLUME_USERNAME"),
                        help="Flume account email [env: FLUME_USERNAME]")
    parser.add_argument("--password",
                        default=os.environ.get("FLUME_PASSWORD"),
                        help="Flume account password [env: FLUME_PASSWORD]")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    # Validate credentials
    missing = [name for name, val in [
        ("--client-id / FLUME_CLIENT_ID", args.client_id),
        ("--client-secret / FLUME_CLIENT_SECRET", args.client_secret),
        ("--username / FLUME_USERNAME", args.username),
        ("--password / FLUME_PASSWORD", args.password),
    ] if not val]
    if missing:
        parser.error(f"Missing required credentials: {', '.join(missing)}")

    return args


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log.info("=== Flume Sync — %s ===", args.date)

    token = get_token(args, args.token_cache)
    user_id = get_user_id(token)
    device_id = get_device_id(token, user_id)
    categories = fetch_categories(token, user_id, device_id, args.date)

    output = build_output(args.date, categories, device_id)
    write_output(args.output, output)

    # Print summary
    log.info("─" * 50)
    log.info("  Date:  %s", output["date"])
    log.info("  Total: %.2f gal", output["total_gallons"])
    for cat, gal in sorted(output["categories"].items(), key=lambda x: -x[1]):
        if gal > 0:
            log.info("  %-12s %.2f gal", cat + ":", gal)
    log.info("─" * 50)
    log.info("Done.")


if __name__ == "__main__":
    main()
