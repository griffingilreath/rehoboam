# ml_service

Analyzes `data/history.json` snapshots produced by `state_engine_service` and emits a divergence score (`data/divergence.json`). The initial implementation uses simple z-scores so it’s transparent and easy to run on a Jetson Nano, but the structure is designed to grow into a more predictive system.

## Current Behavior

- **Features:**
  - `active_leds` – count of LEDs with activity above a threshold
  - `avg_activity` – mean activity level across LEDs
  - `error_count` – number of LEDs in `ERROR`
- **Baseline:** window of `baseline_days` (configurable) used to compute mean + population standard deviation.
- **Output:**
  ```json
  {
    "score": 1.73,
    "level": "caution",
    "metrics": {
      "active_leds": { "value": 6, "mean": 4.2, "stdev": 0.9, "z": 1.98 },
      "avg_activity": { ... },
      "error_count": { ... }
    }
  }
  ```
- **Consumers:** `/divergence` API endpoint, e-paper divergence scene, dashboards.

## Roadmap: Predictive / Proactive Layer

We plan to extend the ML service in stages:

1. **Context capture** – augment `history.json` with extra signals: weather (rain forecast), occupancy, time of day, HA automations (`events.json`), Pi-hole ratio trends, power events (UPS sensors).
2. **Pattern learning** – support rule mining / sequence models:
   - Simple association rules: “If rain forecast + blinds closed daily, but today blinds stayed open → flag.”
   - Time-of-day preference learning: e.g., recommended heat setpoint detected from past behavior.
   - Anomaly models beyond z-scores (Isolation Forest, One-Class SVM, or TF Lite models) for “this cluster of signals is off.”
3. **Recommendations:** write `data/recommendations.json` with entries like:
   ```json
   [
     {
       "timestamp": 1731900000,
       "trigger": "rain_expected",
       "suggestion": "Close living room blinds",
       "confidence": 0.82,
       "status": "pending"
     }
   ]
   ```
   Expose via API (`/recommendations`) so dashboards and HA can act.
4. **Automation hooks:**
   - Publish divergence + recommendations via MQTT or HA REST sensors so automations can respond (“if suggestion == blinds_close, run script.close_blinds unless user overrides”).
   - Provide a feedback loop (mark suggestions as applied/ignored) so the model learns preferences.

## Optional Dependencies

When we enable predictive models, we may add extra requirements:

- `scikit-learn` (rule mining, anomaly detection)
- `statsmodels` (seasonal decomposition)
- `tensorflow-cpu` or `tflite-runtime` (for TF Lite inference)
- `pandas` for richer feature engineering

These will be listed in `jetson/requirements.txt` only when needed; for now the service remains lightweight.

## Config (`config.example.yaml`)

```yaml
data_dir: ./data
canonical_state_filename: canonical_state.json
history_filename: history.json
output_filename: divergence.json
poll_interval_seconds: 5
history_window_seconds: 900
baseline_days: 7
zscore_threshold: 2.5
logging:
  level: INFO
```

Future config additions will include toggles for predictive features (e.g., `enable_recommendations`, `model_path`).
