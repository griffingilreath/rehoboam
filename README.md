# Rehoboam Rack

Modern status wall that turns telemetry from Home Assistant, Pi-hole, and Jetson-hosted agents into a 16-LED panel, dashboards, and e-ink snapshots. This repo contains the full stack: firmware-friendly encoders, API, ML divergence scoring, and display clients.

Key design docs live in [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`SERVICES_AND_AGENTS.md`](SERVICES_AND_AGENTS.md). This README summarizes the operational view.

## System Overview

```
Home Assistant + Pi-hole -> config_sync_service -> led_config.json
                               |
collector_service -> raw_state.json -> state_engine_service -> canonical_state.json
                                                            |-> history.json -> ml_service -> divergence.json
                                                            |-> led_encoder_service -> Teensy
                                                            |-> api_service -> dashboards/e-ink
```

Shared artifacts live under `./data` (config, state, history, divergence, service health, HA events).

## Quick Start (Developer)

```bash
# clone + venv
git clone https://github.com/griffingilreath/rehoboam.git
cd rehoboam
python -m venv .venv && source .venv/bin/activate

# install deps
pip install -r jetson/requirements.txt

# copy sample configs
for svc in config_sync_service collector_service state_engine_service led_encoder_service api_service ml_service; do
  cp jetson/$svc/config.example.yaml jetson/$svc/config.yaml
done

# seed data dir for local testing
mkdir -p data && cp samples/led_config.json data/led_config.json  # optional
```

You can now run the pipeline locally (`python jetson/.../main.py --once`) or enable the provided systemd units once configs are filled out.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `jetson/config_sync_service/` | Pull LED metadata from Home Assistant helpers. |
| `jetson/collector_service/` | Ping devices, gather Pi-hole stats, listen to HA events. |
| `jetson/state_engine_service/` | Convert raw metrics into canonical per-LED state + history. |
| `jetson/led_encoder_service/` | Stream compact frames over serial to the Teensy. |
| `jetson/api_service/` | FastAPI server exposing `/status`, `/config`, `/history`, `/health`, `/info`. |
| `jetson/ml_service/` | Simple divergence scorer (z-score baseline) that writes `divergence.json`. |
| `display_clients/iphone_dashboard/` | Static PWA dashboard for iPhone behind the two-way mirror. |
| `display_clients/eink_client/` | Script that renders grayscale PNGs for e-ink panels. |
| `epaper/` | Modular e-paper scene runner (CLI + config-driven service). |
| `jetson/common/` | Shared utilities (currently heartbeat tracker). |

## Prerequisites

- Jetson Nano (or any Linux host) with Python 3.9+
- [Home Assistant](https://www.home-assistant.io/) + MQTT (for helper entities and events)
- [Pi-hole](https://github.com/pi-hole/AdminLTE#http-api) HTTP API access
- Teensy (Arduino) connected via USB for the LED panel
- Optional: e-ink panel hardware, iPhone kiosk device

Install shared dependencies once:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r jetson/requirements.txt
```

Service-specific dependencies are documented in each directory (e.g., `display_clients/eink_client/requirements.txt`).
If you plan to prototype the e-paper scenes, install the Pillow/IT8951 extras:

```bash
pip install -r epaper/requirements.txt
```

## Configuration & Data Directory

1. Create a writable data directory (default `./data`).
2. Copy each service's `config.example.yaml` → `config.yaml` and edit:
   - Home Assistant URLs/tokens
   - Serial device path and baud rate
   - API host/port, CORS origins
   - ML/History retention thresholds
3. Ensure `data/` is shared by all services so files like `led_config.json`, `raw_state.json`, `canonical_state.json`, `history.json`, `divergence.json`, and `service_health.json` stay in sync.

## Running the Core Services

Typical order (each in its own process/systemd unit):

```bash
python jetson/config_sync_service/main.py --config jetson/config_sync_service/config.yaml
python jetson/collector_service/main.py --config jetson/collector_service/config.yaml
python jetson/state_engine_service/main.py --config jetson/state_engine_service/config.yaml
python jetson/led_encoder_service/main.py --config jetson/led_encoder_service/config.yaml
python jetson/api_service/main.py --config jetson/api_service/config.yaml
python jetson/ml_service/main.py --config jetson/ml_service/config.yaml  # optional but enables divergence visuals
```

All services write heartbeats into `data/service_health.json`. The API reads that file for `/health`, so as long as every process points at the same `data_dir`, the dashboard can show live service status.

### systemd Templates

Sample units live in [`systemd/`](systemd/README.md). After creating `/etc/rehoboam.env` with the appropriate paths (`REHOBOAM_HOME`, `REHOBOAM_VENV`, `REHOBOAM_DATA`), copy the `.service` files into `/etc/systemd/system/`, run `sudo systemctl daemon-reload`, and `enable --now` whichever agents you need. This keeps the stack resilient across reboots and ensures `service_health.json` stays fresh.

### Teensy Firmware

The host-side encoder is ready; pair it with a Teensy sketch that parses frames `{i,h,a,t}` and drives the 16 Neopixels (see `SERVICES_AND_AGENTS.md` §7 for guidance).

### Display Clients

- **iPhone dashboard:** serve `display_clients/iphone_dashboard` (e.g., `python -m http.server 8080 --directory display_clients/iphone_dashboard`) and point Safari at it; override API base via `localStorage.setItem('rehoboam_api', 'http://jetson-rack.local:8000')` if needed.
- **E-ink render:** run `python display_clients/eink_client/render.py --api http://jetson-rack.local:8000 --output /tmp/frame.png` on a timer and push the PNG to your panel.
- **E-paper scenes:** the new `epaper/` module can render animated scenes (standby type-in, activity log, Pi-hole stats, divergence gauge, etc.) either to a fake backend (PNG dumps) or real IT8951 hardware. Run ad hoc via `python -m epaper.cli.main --backend fake --scene divergence` or use the config-driven runner `python -m epaper.service.main --config epaper/config.yaml`.

## Tests & CI

- Unit tests live under `tests/` (currently covering the ML divergence model). Run them with:
  ```bash
  source .venv/bin/activate
  python -m unittest discover -s tests -v
  ```
- GitHub Actions workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) provisions a venv, installs `jetson/requirements.txt`, and executes the test suite on pushes/PRs. Add more suites (lint, integration) by dropping additional YAML files next to it.

## Observability & Logs

- Each service uses Python's `logging`; set `logging.level` in config or pass `--log-level`.
- `service_health.json` entries show `status`, `updated_at`, host, pid, and optional error messages—surface them via API `/health` or inspect directly.
- `events.json` captures normalized Home Assistant events (via `collector_service`) for the e-paper activity feed.
- Files are written atomically (`.tmp` + rename) to keep downstream readers safe.

## Documentation Index

- [`ARCHITECTURE.md`](ARCHITECTURE.md): hardware/network overview, data flow, entity modeling.
- [`SERVICES_AND_AGENTS.md`](SERVICES_AND_AGENTS.md): in-depth specs for every agent, firmware responsibilities, client layouts.
- Service-specific READMEs under `jetson/*/` and `display_clients/*/` cover configuration, operations, and troubleshooting.

## Future Enhancements

- Richer ML/anomaly detection (swap `DivergenceModel` with more advanced time-series models).
- SNMP/managed switch telemetry in `collector_service`.
- WebSocket push channel in `api_service` + dashboard for smoother updates.
- Teensy firmware implementation sharing the same repo (e.g., under `firmware/`).
- E-paper scene scheduler + control surface (e.g., select scenes via API, rotation by time of day).
- Broader automated testing + schema validators for the shared JSON contracts.

Pull requests or ideas should reference the architecture docs to keep the system coherent.
