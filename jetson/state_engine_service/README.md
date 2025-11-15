# state_engine_service

Consumes `led_config.json` and `raw_state.json`, applies deterministic rules for health + activity, and publishes the canonical LED state consumed by the encoder and API services.

## Responsibilities

- Normalize raw metrics into the shared `canonical_state.json` schema.
- Decide `health` (`OK`, `WARNING`, `ERROR`, `OFFLINE`, `UNKNOWN`) based on ping reachability, latency, and HA availability hints.
- Maintain per-LED `activity_level` with smooth decay so animations have inertia.
- Assign `activity_type` hints (`light_change`, `dns_queries`, `none`, etc.) for downstream animations and dashboards.

## Prerequisites

- Python 3.9+ and `pip install -r jetson/requirements.txt`.
- `config_sync_service` + `collector_service` running so `led_config.json` and `raw_state.json` stay current.
- Optional: populate `activity_hint` or `event_entities` fields via Home Assistant helpers to fine-tune behavior.

## Configuration

1. Copy the sample:
   ```bash
   cp jetson/state_engine_service/config.example.yaml jetson/state_engine_service/config.yaml
   ```
2. Key sections:
   - `data_dir`: directory containing the shared JSON files (use absolute path in production).
   - `poll_interval_seconds`: how often to recompute canonical state (2s keeps things responsive).
   - `history_enabled`: toggle writing snapshots to `history.json`.
   - `history_filename`: file that accumulates canonical snapshots (default `history.json` under `data_dir`).
   - `history_max_entries` / `history_retention_seconds`: trim history by count or age to keep files small.
   - `health_rules`:
     - `ping_timeout_ms`: treat higher RTT or missing data beyond this window as potential issues.
     - `warning_latency_ms`: RTT above this threshold yields `WARNING` instead of `OK`.
     - `offline_grace_seconds`: allow this much time after `raw_state` stops updating before declaring `UNKNOWN`.
     - `require_availability_entity`: if `true`, `ha_available == false` forces `ERROR` even if ping succeeds.
   - `activity_rules`:
     - `decay_per_second`: amount the activity level decays every second without events.
     - `event_boost`: contribution per event counted in `events_last_window`.
     - `pihole_qps_scale`: multiplier for Pi-hole QPS to translate into activity.
     - `max_activity`: clamps the final activity level.

### LED Metadata Hooks

`config_sync_service` can add optional fields per LED to guide the state engine:

- `activity_hint`: override default activity type label (`light_change`, `dns_queries`, `blind_move`, etc.).
- `event_entities`: list/comma string of HA entity IDs whose events should boost activity.

## Running

```bash
python jetson/state_engine_service/main.py \
  --config jetson/state_engine_service/config.yaml
```

- Append `--once` for single-cycle testing (useful in CI or unit tests).
- Override logging temporarily with `--log-level DEBUG` when tuning thresholds.

## Output

`canonical_state.json` example:

```json
{
  "generated_at": "2025-11-15T20:07:10.123456+00:00",
  "timestamp": 1731614830,
  "leds": [
    {
      "index": 0,
      "name": "Hue Bridge",
      "health": "OK",
      "activity_level": 0.42,
      "activity_type": "light_change"
    },
    {
      "index": 2,
      "name": "Pi-hole",
      "health": "WARNING",
      "activity_level": 0.87,
      "activity_type": "dns_queries"
    }
  ]
}
```

Downstream services (`led_encoder_service`, dashboards, ML) read this file as the single source of truth. When history logging is enabled, each snapshot is also appended to `history.json` (rolling window) for ML and e-ink clients.

## Operational Notes

- The service caches per-LED state in memory to provide smooth decay; restarting it resets activity levels. If you need persistence, serialize `_per_led_state` on shutdown/startup.
- Missing `led_config.json` or `raw_state.json` triggers warnings but the service keeps running until upstream services populate the files.
- Writes to `canonical_state.json` are atomic (tmp + rename) to keep consumers from reading partial updates.
- Health decisions favor availability sensors when present but fall back to ping reachability.
- Custom health logic is easy to extend: tweak `_determine_health` rules or add new thresholds in the config.
- Each loop updates `service_health.json`, making the API `/health` endpoint aware of state-engine liveness/failures.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Missing led_config or raw_state` warning | Upstream services not running | Start `config_sync_service` and `collector_service` |
| All LEDs stuck at `UNKNOWN` | Raw state timestamp stale or HA down | Verify collector logs, check `offline_grace_seconds` |
| Activity never increases | No `events_last_window` data or thresholds too high | Ensure collector emits event counts, adjust `event_boost` |
| Pi-hole LED health never warns | RTT below `warning_latency_ms` | Lower threshold or inject additional rules |

## Extending

- Track additional health inputs (HTTP checks, SNMP stats) by enriching `_determine_health`.
- Feed divergence/anomaly scores back into `canonical_state.json` by appending extra fields (e.g., `divergence` per LED or globally).
- Emit metrics (Prometheus/StatsD) per LED for observability.

## Next Step

Once `canonical_state.json` is stable, implement `led_encoder_service` to stream compact frames to the Teensy, and `api_service` to expose the canonical data over HTTP/WebSocket.
