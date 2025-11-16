# config_sync_service

Synchronizes LED metadata from Home Assistant helper entities into the Jetson's shared `data/led_config.json` file. Every other Jetson service consumes this canonical config, so keeping it current and reliable is critical.

## Prerequisites

- Python 3.9+ on the Jetson (or dev machine if running remotely).
- `pip install -r jetson/requirements.txt` (installs `requests` + `PyYAML`).
- Home Assistant URL reachable from the Jetson.
- Long-lived access token with permission to read the helper entities (Profile → Long-Lived Access Tokens).
- Helper entities created (e.g. `input_text.led0_name`, `input_text.led0_ip`, etc.) and exposed on a dashboard for easy editing.

**Quick Setup:** See [`docs/home_assistant_helpers.example.yaml`](../../docs/home_assistant_helpers.example.yaml) for a complete example configuration with all 16 LEDs pre-configured. Copy it into your Home Assistant configuration and customize as needed.

## Configuration

1. Copy the sample config:
   ```bash
   cp jetson/config_sync_service/config.example.yaml jetson/config_sync_service/config.yaml
   ```
2. Edit `config.yaml`:
   - `data_dir`: absolute path recommended (e.g. `/opt/rehoboam/data`).
   - `poll_interval_seconds`: how often to refresh from Home Assistant (30–60s is plenty).
   - `led_count`: number of LEDs you expect (default 16).
   - `home_assistant.base_url`: HTTPS preferred; include port.
   - `home_assistant.token`: paste long-lived token.
   - `templates`: format strings for each helper entity; `{index}` placeholder is replaced with `0..led_count-1`.
   - `templates.extra_fields`: optional custom fields to include (notes, rack position, etc.).
   - `defaults`: fallback values when HA fields are blank/missing (e.g. `type: unknown`).
   - `logging.level`: `INFO` for normal use, `DEBUG` for troubleshooting.

### Template Tips

- You can mix helper types: `input_text` for free text, `input_select` for controlled vocab, `input_boolean` for flags.
- Omit a field entirely by leaving the template blank or removing it. (The service ignores empty template strings.)
- If Home Assistant uses zero-padded helpers (`led00_name`), reflect that in the template: `input_text.led{index:02d}_name`.

## Running

```bash
python jetson/config_sync_service/main.py \
  --config jetson/config_sync_service/config.yaml
```

- Add `--once` to perform a single sync (useful for CI/tests).
- Override log level temporarily with `--log-level DEBUG`.
- Deploy under systemd by pointing ExecStart at the command above. Ensure `WorkingDirectory` is the repo root (or adjust `--config` paths).

## Output

- Writes `led_config.json` atomically into `data_dir` (default `./data/led_config.json`).
- Payload shape:
  ```json
  {
    "generated_at": "2025-11-15T18:22:07.123456+00:00",
    "leds": [
      {
        "index": 0,
        "name": "Hue Bridge",
        "type": "bridge",
        "ip": "192.168.1.10",
        "ha_availability_entity": "binary_sensor.hue_bridge_available",
        "notes": "Rack 1"
      }
    ]
  }
  ```
- Fields beyond `index/name/type` come from helper templates or defaults. Unknown/blank values are skipped so downstream services can rely on clean data.

## Operational Notes

- The service tracks the last serialized payload and only rewrites the file when data changes. Downstream watchers can rely on file modification time to detect updates.
- CTRL+C or `systemctl stop` triggers a graceful shutdown that finishes the current poll cycle before exiting.
- If Home Assistant is unreachable, the service logs a warning and keeps the previous config; it does not clear LEDs to avoid breaking other agents.
- Use `journalctl -u config-sync` (or your supervisor logs) to monitor warnings about missing helper entities.
- On every successful cycle the service updates `service_health.json` (via the shared `ServiceHealthTracker`) so the API/dashboard can surface its status; failures mark the entry as `error`.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Configuration file not found` | Forgot to copy `config.example.yaml` | Create `config.yaml` and rerun |
| `Template for 'name' is required` | Removed `templates.name` entry | Restore `name` template; it's mandatory |
| `Home Assistant entity ... not found` | Helper entity typo or outside `led_count` range | Verify entity IDs in HA; adjust templates or increase `led_count` |
| `led_config.json` missing fields | Helper returned empty state and no default supplied | Set defaults or fill in HA dashboard |
| SSL errors | Self-signed HA cert | Set `verify_ssl: false` (or install CA cert on Jetson) |

## Extending

- Add more fields by listing them under `templates.extra_fields` and referencing new helpers (e.g. `rack_unit`, `icon`).
- If you add a second HA instance, run multiple copies with different configs but distinct `data_dir` targets.
- Wrap the service in a container: mount `/app/data` for shared JSON files, inject config via secrets/ConfigMap.

## Next Steps

With `led_config.json` in place, the `collector_service` can map telemetry to LED definitions, and the `state_engine_service` can emit canonical states. Keep this service running anywhere the HA config may change so the physical panel stays in sync.
