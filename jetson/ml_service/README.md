# ml_service

Future-facing service that reads canonical state history and computes a simple divergence score (z-score based) to approximate the “Rehoboam” anomaly signal described in the architecture doc.

## Responsibilities

- Consume a rolling `history.json` (or similar) produced by `state_engine_service` or a future logging agent.
- Compute summary metrics (active LED count, average activity, error counts) over time.
- Compare the latest metrics against a baseline window to produce a z-score-based divergence indicator.
- Write the result to `divergence.json` (or append back into `canonical_state.json` in a future revision).

## Prerequisites

- Python 3.9+ and `pip install -r jetson/requirements.txt`.
- A history file containing recent canonical snapshots (e.g., `history.json` with an `entries` array).
- Optional: Extend the history writer to include more metrics; this service is agnostic to the logging mechanism as long as timestamps and LED fields are present.

## Configuration

1. Copy the template:
   ```bash
   cp jetson/ml_service/config.example.yaml jetson/ml_service/config.yaml
   ```
2. Adjust:
   - `data_dir`: base path for canonical/history/divergence files.
   - `history_window_seconds`: how far back to look for scoring (default 15 minutes).
   - `baseline_days`: days of history to use when computing baseline statistics.
   - `zscore_threshold`: z-score threshold for flagging divergence (`>= threshold` → `divergent`, `>= threshold/2` → `caution`).
   - `poll_interval_seconds`: cadence for recomputing the score.

## Running

```bash
python jetson/ml_service/main.py \
  --config jetson/ml_service/config.yaml
```

- Add `--once` to calculate a single score (good for CI/experiments).
- Override log level temporarily with `--log-level DEBUG`.

## Output

`divergence.json` example:

```json
{
  "generated_at": "2025-11-15T21:10:12.123456+00:00",
  "timestamp": 1731618612,
  "score": 1.73,
  "level": "caution",
  "metrics": {
    "active_leds": {"value": 6, "mean": 4.2, "stdev": 0.9, "z": 1.98},
    "avg_activity": {"value": 0.44, "mean": 0.25, "stdev": 0.07, "z": 2.71},
    "error_count": {"value": 1, "mean": 0.3, "stdev": 0.4, "z": 1.75}
  }
}
```

You can ingest this into `api_service` (e.g., add `/divergence`) or feed it back into `canonical_state.json` as an extra field per LED/global.

## Operational Notes

- This skeleton intentionally uses straightforward statistics so it runs fast on a Jetson Nano without heavy dependencies.
- Baseline uses the last `baseline_days` worth of data inside the available history; prune history periodically to keep the file size manageable.
- If `history.json` is missing, malformed, or empty, the service logs a warning and waits for the next interval.
- Extend `_extract_metrics` to include more complex signals (per-LED divergence, Pi-hole flux, etc.).
- For advanced ML, swap `DivergenceModel` with a more sophisticated model (e.g., scikit-learn, TinyML) while keeping the same input/output contract.
- Each scoring loop reports its health to `service_health.json`, meaning the API `/health` endpoint can highlight ML outages.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `No history available yet` warnings | Upstream logger not producing history | Implement history writer or adjust paths |
| `history file is not a list` logs | Unexpected schema | Ensure history has `entries` array or pure list |
| Score always zero | Baseline stdev is zero (constant data) | Extend baseline window or add more varied metrics |

## Next Step

Integrate `divergence.json` into `api_service` and dashboards (e.g., show a “Rehoboam” cluster or dedicated LED animation). When ready, replace the simple statistical model with a richer anomaly detector while keeping the same file contract.
