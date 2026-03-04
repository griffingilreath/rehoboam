"""
flume_sync.py — AppDaemon app for daily Flume water category sync.

Runs every day at 02:05 AM, queries the Flume portal API for yesterday's
categorized water usage, and writes sensors directly into Home Assistant.

Sensors created in HA (state machine):
  sensor.flume_yesterday_total     — total gallons, attributes: date, synced_at
  sensor.flume_yesterday_shower    — shower gallons
  sensor.flume_yesterday_toilet
  sensor.flume_yesterday_faucet
  sensor.flume_yesterday_irrigation
  sensor.flume_yesterday_bathtub
  sensor.flume_yesterday_laundry
  sensor.flume_yesterday_dishwasher
  sensor.flume_yesterday_other
  sensor.flume_yesterday_leak

After a successful sync, fires the HA event:
  flume_sync_complete
  payload: { date: "YYYY-MM-DD", total_gallons: 45.2, categories: {...} }

This event triggers the lifetime accumulation automation in water_flume.yaml.

Installation:
  1. Install AppDaemon add-on in Home Assistant Supervisor
  2. Copy this file to /addon_configs/appdaemon/apps/flume_sync.py
  3. Add the entry below to /addon_configs/appdaemon/apps/apps.yaml
  4. Add credentials to /addon_configs/appdaemon/appdaemon.yaml secrets section
     or use the AppDaemon secrets.yaml (see README.md)
  5. Restart AppDaemon

apps.yaml entry:
  flume_sync:
    module: flume_sync
    class: FlumeSyncApp
    client_id: !secret flume_client_id
    client_secret: !secret flume_client_secret
    username: !secret flume_username
    password: !secret flume_password
    run_on_startup: false   # set true temporarily to test immediately
"""

import time
from datetime import date, datetime, timedelta, timezone

import appdaemon.plugins.hass.hassapi as hass
import requests

BASE_URL = "https://api.flumetech.com"

# Flume category IDs → sensor name suffixes
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


class FlumeSyncApp(hass.Hass):
    def initialize(self):
        # Schedule daily sync at 02:05 AM (after Flume processes prior-day data)
        self.run_daily(self.sync_flume, "02:05:00")

        # Optional: run shortly after startup for testing
        if self.args.get("run_on_startup", False):
            self.run_in(self.sync_flume, 10)

        # Token cache: persisted in-memory for the process lifetime
        self._token: str | None = None
        self._token_expires_at: float = 0.0

        self.log("FlumeSyncApp initialized — daily sync scheduled at 02:05")

    # ── Public entry point ────────────────────────────────────────────────────

    def sync_flume(self, kwargs):
        """Main sync entry point — called by scheduler or on startup."""
        target_date = date.today() - timedelta(days=1)
        self.log(f"Starting Flume sync for {target_date}")

        try:
            token = self._get_token()
            user_id = self._get_user_id(token)
            device_id = self._get_device_id(token, user_id)
            categories = self._fetch_categories(token, user_id, device_id, target_date)
            self._publish_sensors(target_date, categories)
            self.log(
                f"Flume sync complete — {target_date}: "
                f"{sum(categories.values()):.2f} gal total"
            )
        except FlumeAuthError as exc:
            self.log(f"Flume auth failed: {exc}", level="ERROR")
            self.call_service(
                "notify/notify",
                title="Flume Sync: Auth Failed",
                message=f"Check your Flume credentials in AppDaemon apps.yaml. Error: {exc}",
            )
        except FlumeAPIError as exc:
            self.log(f"Flume API error: {exc}", level="ERROR")
            self.call_service(
                "notify/notify",
                title="Flume Sync: API Error",
                message=f"Flume may be temporarily down. Error: {exc}",
            )
        except Exception as exc:
            self.log(f"Unexpected error during Flume sync: {exc}", level="ERROR")
            self.call_service(
                "notify/notify",
                title="Flume Sync: Unexpected Error",
                message=str(exc),
            )

    # ── Token management ──────────────────────────────────────────────────────

    def _get_token(self) -> str:
        """Return a valid Bearer token, re-authenticating only when expired."""
        if self._token and time.time() < self._token_expires_at - 300:
            return self._token

        self.log("Authenticating with Flume API...")
        try:
            resp = requests.post(
                f"{BASE_URL}/oauth/token",
                json={
                    "grant_type": "password",
                    "client_id": self.args["client_id"],
                    "client_secret": self.args["client_secret"],
                    "username": self.args["username"],
                    "password": self.args["password"],
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            raise FlumeAPIError(f"Network error during auth: {exc}") from exc

        if resp.status_code == 401:
            raise FlumeAuthError("Invalid credentials (401)")
        if not resp.ok:
            raise FlumeAPIError(f"Auth returned HTTP {resp.status_code}")

        body = resp.json()
        token_obj = body["data"][0] if isinstance(body.get("data"), list) else body
        self._token = token_obj["access_token"]
        self._token_expires_at = time.time() + int(token_obj.get("expires_in", 3600))
        self.log(
            f"Auth OK — token valid for {int(token_obj.get('expires_in', 3600)) // 60} min"
        )
        return self._token

    # ── API helpers ───────────────────────────────────────────────────────────

    def _api_get(self, token: str, path: str, params: dict | None = None) -> dict:
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
            raise FlumeAPIError(f"GET {path} failed: {exc}") from exc

    def _api_post(self, token: str, path: str, payload: dict) -> dict:
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
            raise FlumeAPIError(f"POST {path} failed: {exc}") from exc

    def _get_user_id(self, token: str) -> str:
        body = self._api_get(token, "/me")
        user_id = body["data"][0]["id"]
        self.log(f"User ID: {user_id}", level="DEBUG")
        return user_id

    def _get_device_id(self, token: str, user_id: str) -> str:
        body = self._api_get(token, "/me/devices", params={
            "user_id": user_id,
            "location": "true",
            "list_shared": "true",
        })
        for device in body.get("data", []):
            if device.get("type") == 2:   # Type 2 = Flume 2 Smart Water Sensor
                location = device.get("location", {}).get("name", "unknown")
                self.log(f"Found device {device['id']} at '{location}'")
                return device["id"]
        raise FlumeAPIError("No Flume 2 water monitor found in your account")

    # ── Category query ────────────────────────────────────────────────────────

    def _fetch_categories(
        self, token: str, user_id: str, device_id: str, target_date: date
    ) -> dict[str, float]:
        since = f"{target_date} 00:00:00"
        until = f"{target_date} 23:59:59"

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

        self.log(f"Querying {len(queries)} categories for {target_date}...")
        body = self._api_post(
            token,
            f"/me/users/{user_id}/devices/{device_id}/query",
            {"queries": queries},
        )

        results: dict[str, float] = {name: 0.0 for name in CATEGORIES.values()}
        for item in body.get("data", []):
            cat_name = item.get("request_id")
            if cat_name not in results:
                continue
            values = item.get("value") or []
            total = sum(
                float(v.get("value", 0)) for v in values if v.get("value") is not None
            )
            results[cat_name] = round(total, 3)

        return results

    # ── HA sensor publishing ──────────────────────────────────────────────────

    def _publish_sensors(self, target_date: date, categories: dict[str, float]) -> None:
        total = round(sum(categories.values()), 3)
        synced_at = datetime.now(timezone.utc).isoformat()

        # Write the total sensor with date + synced_at metadata
        self.set_state(
            "sensor.flume_yesterday_total",
            state=total,
            attributes={
                "unit_of_measurement": "gal",
                "device_class": "water",
                "state_class": "total",
                "friendly_name": "Water Yesterday: Total",
                "date": str(target_date),
                "synced_at": synced_at,
            },
        )

        # Write one sensor per category
        friendly_names = {
            "shower": "Water Yesterday: Shower",
            "toilet": "Water Yesterday: Toilet",
            "faucet": "Water Yesterday: Faucet",
            "irrigation": "Water Yesterday: Irrigation",
            "bathtub": "Water Yesterday: Bathtub",
            "laundry": "Water Yesterday: Laundry",
            "dishwasher": "Water Yesterday: Dishwasher",
            "other": "Water Yesterday: Other",
            "leak": "Water Yesterday: Leak",
        }
        for cat_name, gallons in categories.items():
            self.set_state(
                f"sensor.flume_yesterday_{cat_name}",
                state=round(gallons, 3),
                attributes={
                    "unit_of_measurement": "gal",
                    "device_class": "water",
                    "state_class": "measurement",
                    "friendly_name": friendly_names.get(cat_name, cat_name),
                },
            )

        # Fire HA event for water_flume.yaml automation to accumulate lifetime totals
        self.fire_event(
            "flume_sync_complete",
            date=str(target_date),
            total_gallons=total,
            categories=categories,
        )

        self.log(
            f"Published {len(categories) + 1} sensors — total: {total:.2f} gal"
        )
        for cat, gal in sorted(categories.items(), key=lambda x: -x[1]):
            if gal > 0:
                self.log(f"  {cat:<12} {gal:.2f} gal", level="DEBUG")


# ── Custom exceptions ─────────────────────────────────────────────────────────

class FlumeAuthError(Exception):
    """Raised when authentication fails (bad credentials)."""


class FlumeAPIError(Exception):
    """Raised when the Flume API returns an error or is unreachable."""
