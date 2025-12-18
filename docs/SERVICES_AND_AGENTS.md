# SERVICES_AND_AGENTS.md

This document describes each service/agent in detail so implementations can be generated consistently.

All Jetson services are expected to be:

- Written in **Python 3**.
- Runnable as `python main.py` (from the service directory or root).
- Configurable via:
  - A simple `config.yaml` or environment variables (defaults to `config.yaml` in the service directory).
  - Shared JSON files in a `data/` directory (or similar).
- Graceful if dependencies (HA, Pi-hole, serial device) are not yet available.

Directories are assumed to live under `jetson/` unless noted otherwise.

## Common Conventions

- **Data dir** (example): `./data/`
  - `led_config.json`
  - `raw_state.json`
  - `canonical_state.json`
- **Logging**: use `logging` module, log to stdout by default.
- **JSON**: use snake_case keys, UTF-8, no BOM.
- **Intervals**:
  - Telemetry collection: every 1–3 seconds.
  - State engine update: same or slightly offset.
  - LED frames: up to ~10 frames/second; can be lower if changes are infrequent.

---

## 1. Config Agent – `config_sync_service`

Path: `jetson/config_sync_service/main.py`

**Responsibility**

- Maintain a local `led_config.json` that describes:
  - What each LED (0–15) represents.
  - IP addresses and types (bridge, pihole, server, etc.).
  - Relevant HA availability entities.

**Inputs**

- Home Assistant helper entities, e.g.:
  - `input_text.led0_name`
  - `input_text.led0_ip`
  - `input_select.led0_type`
- Optionally: HA may also contain helper fields for HA availability entity names.

**Output**

`./data/led_config.json`:
