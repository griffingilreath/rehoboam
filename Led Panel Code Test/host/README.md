# Host Supervisor

Python-based services that monitor network and smart home data sources, then instruct the Teensy over USB serial.

## Layout
- `scripts/monitors/` – independent check modules (ping, MQTT, API integrations).
- `scripts/protocol/` – serial client, framing/parsing helpers, message builders.
- `services/` – orchestration entry points (e.g., `supervisor.py`, systemd service wrappers).
- `config/` – YAML/JSON configuration for devices, thresholds, and protocol tuning.
- `tests/` – pytest-based unit and integration tests.

## Quick Start
1. Create a Python virtualenv and install dependencies (to be defined in `requirements.txt`).
2. Run `python services/supervisor.py` to start the monitoring loop.
3. Use `scripts/protocol/mock_host.py` (to be added) for manual testing against the Teensy firmware.
