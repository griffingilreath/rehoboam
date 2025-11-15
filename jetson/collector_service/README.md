# collector_service

Collects raw device telemetry (reachability, Home Assistant availability, Pi-hole stats, and recent events) and writes the shared `raw_state.json` consumed by the state engine.

## Responsibilities

- Load the latest `led_config.json` so device metadata stays synced.
- Ping each device to determine reachability/latency.
- Query Home Assistant availability binary sensors (if defined per device).
- Pull Pi-hole stats for LEDs whose `type` is `pihole`.
- Stream Home Assistant `state_changed` events and keep a short rolling buffer for activity counts.
- Emit `raw_state.json` with `devices` + `events` sections at a steady cadence.

## Prerequisites

- Python 3.9+ and `pip install -r jetson/requirements.txt` (needs `requests`, `PyYAML`, `websocket-client`).
- `config_sync_service` already producing `data/led_config.json`.
- Home Assistant long-lived token and reachable base URL.
- Optional Pi-hole API token (recommended) if monitoring Pi-hole devices.
- `ping` binary available (default on Linux/macOS; on Windows it also works out-of-the-box).

## Configuration

1. Copy and edit the sample config:
   ```bash
   cp jetson/collector_service/config.example.yaml jetson/collector_service/config.yaml
   ```
2. Key fields:
   - `data_dir`: path containing `led_config.json` and where `raw_state.json` will be written (absolute path recommended in production).
   - `poll_interval_seconds`: loop cadence (1–3 seconds keeps LEDs fresh without spamming HA/Pi-hole).
   - `event_buffer_seconds`: size of the rolling window used for activity counts.
   - `home_assistant`: base URL, token, SSL behavior, and optional mapping for states that count as "available".
   - `pihole`: set `enabled: true`, `base_url`, and `token` (if auth required). Leave disabled for non-Pi-hole setups.
   - `ping`: tweak `timeout_seconds` for devices on slower links.
   - `events`: set `enabled: false` to skip websocket streaming (e.g., offline dev environments).

### LED-Specific Fields

`collector_service` looks for extra keys inside each LED entry (as produced by `config_sync_service`):

- `ha_availability_entity`: binary sensor entity ID to determine availability (e.g., `binary_sensor.hue_bridge_available`).
- `event_entities`: comma-separated string or list of entity IDs to count events for (e.g., `["light.office_lamp", "switch.office_relay"]`).
- `type`: when set to `pihole`, Pi-hole API stats are attached to that device entry.

You can add these helpers to Home Assistant and include them via `config_sync_service` `templates.extra_fields`.

## Running

```bash
python jetson/collector_service/main.py \
  --config jetson/collector_service/config.yaml
```

- `--once` collects a single snapshot (handy for debugging).
- `--log-level DEBUG` temporarily increases verbosity without editing config.
- Under systemd, make sure `WorkingDirectory` points to the repo root so relative paths resolve; or use absolute paths in `config.yaml`.

## Output Format

`data/raw_state.json` (example):

```json
{
  "timestamp": 1731612345,
  "generated_at": "2025-11-15T19:40:12.123456+00:00",
  "devices": {
    "Hue Bridge": {
      "reachable": true,
      "rtt_ms": 11.5,
      "ha_available": true,
      "events_last_window": 3
    },
    "Pi-hole": {
      "reachable": true,
      "qps": 34.2,
      "blocked_ratio": 0.21,
      "pihole_status": "enabled"
    }
  },
  "events": [
    {
      "timestamp": 1731612343.12,
      "source": "HomeAssistant",
      "kind": "state_changed",
      "entity_id": "light.office_lamp"
    }
  ]
}
```

## Operational Notes & Tips

- The service reloads `led_config.json` every cycle so edits in Home Assistant propagate immediately.
- Writes to `raw_state.json` are atomic (tmp file + rename) to avoid partially-written files for downstream readers.
- When Home Assistant or Pi-hole calls fail, warnings are logged and the previous values stay untouched; this prevents flapping states.
- Event streaming uses HA's websocket API. If HA restarts, the service automatically reconnects with exponential backoff controlled by `events.reconnect_delay_seconds`.
- `events_last_window` counts only the entity IDs explicitly listed in `event_entities`. Leave the field blank if you don't care about event-driven activity for that LED.
- Pi-hole `blocked_ratio` is computed as `ads_blocked_today / max(dns_queries_today, 1)` to avoid divide-by-zero.
- `ping` behavior adapts to Windows vs. POSIX automatically; ensure ICMP is allowed in your network policies.
- Heartbeats are written to `service_health.json` on every successful loop so the API can surface collector status; errors flip the recorded status to `error` for quick diagnosis.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `No led_config.json available yet` | Config sync service not running | Start `config_sync_service` or manually place the file |
| `Invalid JSON in led_config.json` | File truncated or edited manually | Regenerate from HA helpers |
| Event stream reconnect spam | Wrong HA URL/token | Verify `home_assistant` settings; test with curl/wscat |
| Pi-hole stats missing | `type` not set to `pihole` or token missing | Update HA helpers/templates accordingly |
| `Ping command failed` | Ping binary missing | Install `iputils-ping` (Linux) or adjust firewall |

## Extending

- Add SNMP polling by enriching `CollectorService._collect_device_state` for LEDs tagged with `type: switch`.
- Persist events to a queue (Redis/MQTT) by hooking into `EventBuffer.add` when you need deeper analytics.
- Support alternate activity sources (e.g., Pi-hole log tail) by appending entries to the shared event buffer.

## Next Step

With `raw_state.json` updated in real time, proceed to build `state_engine_service` to translate raw metrics into the canonical LED state consumed by the encoder and API services.
