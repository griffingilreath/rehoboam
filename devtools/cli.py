#!/usr/bin/env python3
"""Lightweight CLI summary for Rehoboam data files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_DATA_DIR = Path("data")


def load_json(path: Path) -> Dict[str, Any] | List[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - debug helper
        print(f"Failed to read {path}: {exc}")
        return None


def summarize_status(status: Dict[str, Any]) -> None:
    leds = status.get("leds", []) if status else []
    print("\nLED PANEL")
    if not leds:
        print("  (no data)")
    for led in leds:
        name = led.get("name") or f"LED {led.get('index')}"
        health = led.get("health", "UNKNOWN")
        activity = led.get("activity_level", 0)
        print(f"  {name:<18} | {health:<8} | activity={activity:.2f} | type={led.get('type', 'n/a')}")

    context = status.get("context") if status else None
    if context:
        flags = context.get("flags", {})
        print("\nCONTEXT")
        print(f"  Daypart: {context.get('daypart', 'n/a')}")
        print(f"  Occupied: {flags.get('occupied')}")
        print(f"  Rain expected: {flags.get('rain_expected')}")


def summarize_divergence(divergence: Dict[str, Any]) -> None:
    print("\nDIVERGENCE")
    if not divergence:
         print("  (no data)")
         return
    score = divergence.get("score")
    level = divergence.get("level")
    print(f"  Score: {score}  Level: {level}")
    recs = divergence.get("recommendations", [])
    if recs:
        print("  Recommendations:")
        for rec in recs[:5]:
            print(f"    - {rec.get('suggestion')} → {rec.get('target')} (trigger={rec.get('trigger')}, conf={rec.get('confidence')})")


def summarize_events(events_path: Path) -> None:
    data = load_json(events_path)
    events = data.get("events", []) if isinstance(data, dict) else []
    print("\nRECENT EVENTS")
    if not events:
        print("  (none)")
        return
    for evt in events[-5:][::-1]:
        print(f"  {evt.get('timestamp')} | {evt.get('friendly_name') or evt.get('entity_id')} | {evt.get('summary')}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dev CLI for Rehoboam data files")
    parser.add_argument("--data", default=str(DEFAULT_DATA_DIR), help="Path to data directory")
    args = parser.parse_args(argv)

    data_dir = Path(args.data)
    status = load_json(data_dir / "canonical_state.json") or load_json(data_dir / "raw_state.json")
    summarize_status(status or {})

    divergence = load_json(data_dir / "divergence.json") or {}
    summarize_divergence(divergence)

    summarize_events(data_dir / "events.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
