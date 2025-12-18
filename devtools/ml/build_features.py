#!/usr/bin/env python3
"""Build a features.json artifact from an existing history.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jetson.ml_service.main import FeatureStoreBuilder
from jetson.common.json_store import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Build features.json from history.json")
    parser.add_argument("--history", default="data/history.json", help="Path to history.json")
    parser.add_argument("--output", default="data/features.json", help="Path to write features.json")
    parser.add_argument("--max-entries", type=int, default=5000, help="Max history entries to include")
    args = parser.parse_args()

    history_path = Path(args.history).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not history_path.exists():
        raise SystemExit(f"History file not found: {history_path}")

    payload = json.loads(history_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise SystemExit("history file does not contain a list of entries")

    builder = FeatureStoreBuilder()
    features = builder.build(entries, max_entries=args.max_entries)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_path, features)
    print(f"Wrote {output_path} with {len(features.get('entries', []))} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
