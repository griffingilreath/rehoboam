# epaper

Modular framework for rendering scenes on the IT8951 e-paper panel (or a fake backend for development).

## Components

- `backends/`
  - `fake_backend.py`: dumps frames to `/tmp/epaper_frames/` for quick iteration.
  - `spi_backend.py`: uses the `it8951` Python library to drive the panel via SPI.
  - `usb_backend.py`: streams frames to the external `it8951usb` binary over USB.
- `core/`
  - `display.py`: orchestrates full/partial refreshes and sleep.
  - `renderer.py`: Pillow helpers (blank canvas, centered text, wipe masks).
  - `scene.py`: base class for frame generators.
  - `modes.py`: waveform constants (`GC16`, `DU`).
- `scenes/`
  - `StandbyScene`: REHOBOAM type-in + wipe animation.
  - `ActivityLogScene`: Notification-style list sourced from `data/events.json`.
- `cli/main.py`: argparse entrypoint to pick backend + scene.

## Usage

Install extras:

```bash
pip install -r epaper/requirements.txt
```

Run with the fake backend (writes PNGs to `/tmp/epaper_frames`):

```bash
python -m epaper.cli.main --backend fake --scene standby --text "REHOBOAM"
python -m epaper.cli.main --backend fake --scene activity_log
python -m epaper.cli.main --backend fake --scene pihole
python -m epaper.cli.main --backend fake --scene divergence
```

When hardware is ready:

```bash
python -m epaper.cli.main --backend spi  # requires it8951 Python lib
# or
python -m epaper.cli.main --backend usb  # requires bin/it8951usb helper
```

Config-driven runner (handy for systemd):

```bash
cp epaper/config.example.yaml epaper/config.yaml
python -m epaper.service.main --config epaper/config.yaml
```

## Data inputs

- `ActivityLogScene` expects `data/events.json` with structure:

```json
{
  "events": [
    {
      "timestamp": "2025-05-01T12:34:56+00:00",
      "entity_id": "light.office_lamp",
      "friendly_name": "Office Lamp",
      "domain": "light",
      "summary": "Brightness → 86%",
      "actor": "Griffin"
    }
  ]
}
```

`collector_service` now writes this file automatically when HA events are enabled.

## Next steps

- Add additional scenes (Pi-hole live stats, divergence visualizer, generative art).
- Wire scene selection into `api_service` or a simple commander so you can switch modes without SSH.
- Optimize partial update regions for smoother animations once hardware is available.
