#!/usr/bin/env python3
"""Replay divergence scoring over history.json for offline evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jetson.ml_service.main import DivergenceModel


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay divergence model over history.json")
    parser.add_argument("--history", default="data/history.json", help="Path to history.json")
    parser.add_argument("--bucket", default="global", choices=["global", "daypart"], help="Baseline bucket")
    parser.add_argument("--method", default="standard", choices=["standard", "robust"], help="Baseline method")
    parser.add_argument("--score-method", default="max", choices=["max", "weighted_mean"], help="Score composition")
    parser.add_argument("--threshold", type=float, default=2.5, help="Z-score threshold for caution/divergent")
    parser.add_argument("--baseline-days", type=int, default=7, help="Baseline days")
    args = parser.parse_args()

    history_path = Path(args.history).expanduser().resolve()
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else payload
    if not isinstance(entries, list) or not entries:
        raise SystemExit("history does not contain entries[]")

    model = DivergenceModel(
        baseline_days=args.baseline_days,
        threshold=args.threshold,
        baseline_bucket=args.bucket,
        baseline_method=args.method,
        score_method=args.score_method,
    )

    levels = {"normal": 0, "caution": 0, "divergent": 0, "unknown": 0}
    last = None
    for i in range(5, len(entries) + 1):
        window = entries[:i]
        last = model.score(window)
        levels[last.get("level", "unknown")] = levels.get(last.get("level", "unknown"), 0) + 1

    print("Replay complete")
    print(f"  Snapshots scored: {sum(levels.values())}")
    print(f"  Levels: {levels}")
    if last:
        print(f"  Last score: {last.get('score')} level={last.get('level')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

