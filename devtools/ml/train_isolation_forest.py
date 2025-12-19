#!/usr/bin/env python3
"""Train an IsolationForest model from features.json and write versioned artifacts.

This script is intentionally optional: it requires scikit-learn. If it's not installed,
the script exits with a clear message.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List


def _load_features(path: Path) -> tuple[list[str], list[list[float]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("features.json must be an object")
    feature_list = payload.get("feature_list") or []
    entries = payload.get("entries") or []
    if not isinstance(feature_list, list) or not all(isinstance(x, str) for x in feature_list):
        raise ValueError("features.json missing feature_list[]")
    if not isinstance(entries, list):
        raise ValueError("features.json missing entries[]")
    vectors: List[List[float]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        vec = entry.get("vector")
        if not isinstance(vec, list):
            continue
        try:
            vectors.append([float(x) for x in vec])
        except (TypeError, ValueError):
            continue
    if not vectors:
        raise ValueError("No vectors found in features.json")
    return feature_list, vectors


def main() -> int:
    parser = argparse.ArgumentParser(description="Train IsolationForest from features.json")
    parser.add_argument("--features", default="data/features.json", help="Path to features.json")
    parser.add_argument("--out-dir", default="data/models/isolation_forest", help="Output base directory")
    parser.add_argument("--contamination", type=float, default=0.05, help="Expected anomaly fraction")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    try:
        from sklearn.ensemble import IsolationForest  # type: ignore
        import sklearn  # type: ignore
    except Exception:
        raise SystemExit(
            "scikit-learn is required for training. Install with: python3 -m pip install scikit-learn"
        )

    features_path = Path(args.features).expanduser().resolve()
    if not features_path.exists():
        raise SystemExit(f"features.json not found: {features_path}")

    feature_list, vectors = _load_features(features_path)

    # Basic training distribution stats for drift checks.
    import statistics

    cols = list(zip(*vectors))
    means = [float(statistics.mean(col)) for col in cols]
    stdevs = [float(statistics.pstdev(col)) for col in cols]

    model = IsolationForest(
        n_estimators=200,
        contamination=max(0.001, min(0.5, float(args.contamination))),
        random_state=int(args.seed),
    )
    model.fit(vectors)

    # Convert score_samples (higher=inlier) into anomaly score (higher=more anomalous).
    scores = [-float(s) for s in model.score_samples(vectors)]
    scores_sorted = sorted(scores)

    def percentile(q: float) -> float:
        if not scores_sorted:
            return 0.0
        q = max(0.0, min(1.0, q))
        idx = int(round(q * (len(scores_sorted) - 1)))
        return float(scores_sorted[idx])

    thresholds = {
        "caution": percentile(0.95),
        "divergent": percentile(0.99),
    }

    model_version = time.strftime("%Y%m%d_%H%M%S")
    out_base = Path(args.out_dir).expanduser().resolve()
    version_dir = out_base / model_version
    latest_dir = out_base / "latest"
    version_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)

    import pickle

    # SECURITY: pickle is unsafe. Ensure the output directory has restricted permissions.
    # Future improvements should switch to skops or ONNX.
    model_bytes = pickle.dumps(model)
    (version_dir / "model.pkl").write_bytes(model_bytes)
    (latest_dir / "model.pkl").write_bytes(model_bytes)

    metadata: Dict[str, Any] = {
        "model_type": "isolation_forest",
        "model_version": model_version,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sklearn_version": getattr(sklearn, "__version__", None),
        "feature_list": feature_list,
        "n_samples": len(vectors),
        "contamination": float(args.contamination),
        "thresholds": thresholds,
        "training_stats": {
            "mean": means,
            "stdev": stdevs,
        },
    }
    (version_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (latest_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote model to {version_dir} and updated {latest_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

