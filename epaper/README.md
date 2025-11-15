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

## IT8951 Setup

### SPI backend

1. Install the Python driver (`pip install it8951`). The backend wraps `AutoEPDDisplay` from the open-source driver published by Greg Meyer (see [`GregDMeyer/IT8951`](https://github.com/GregDMeyer/IT8951)).  
2. Wire the panel’s SPI pins to the Jetson/Pi per the Waveshare pinout (3.3V, GND, SCK, MOSI, MISO, CS, HRDY, RST).  
3. Run `python -m epaper.cli.main --backend spi --scene standby`. The driver auto-detects width/height from the panel.

### USB backend

1. Build the `it8951usb` helper from the official Waveshare sample repo (`git clone https://github.com/waveshare/IT8951 && make it8951usb`). Copy the binary into `bin/` or any location on `$PATH`.  
2. Plug the panel into USB (it shows up as `/dev/sg*`).  
3. Use `--backend usb` and override device/tool if needed: `python -m epaper.cli.main --backend usb --backend-option device=/dev/sg1 --backend-option tool=/opt/it8951usb`.

### Partial updates & higher refresh modes

- The IT8951 controller exposes multiple waveforms: `DU` (fast monochrome partial refresh), `GC16` (16-level grayscale full refresh), `GL16`/`GLR16` (ghost-reduction variants). The Waveshare docs describe typical timings (`DU` ≈ 150 ms, `GC16` ≈ 1 s) [^waveshare].  
- In code, `DisplayManager.partial(..., mode="DU")` triggers the faster waveform for animations like typing or notifications. After a sequence of partials, issue a `manager.full(..., mode="GC16")` to “clean” the panel and avoid ghosting.  
- For very high refresh prototypes (e.g., Pi-hole live feed), combine small bounding boxes with partial updates to minimize flashing.

[^waveshare]: See the official [Waveshare IT8951 examples](https://github.com/waveshare/IT8951) for waveform descriptions and timing charts.

### Configuring backend parameters

`epaper/config.yaml` supports a `backend_config` dictionary. Example:

```yaml
backend: usb
backend_config:
  device: /dev/sg0
  tool: /opt/it8951usb
  size: [1872, 1404]
scene: activity_log
```

The CLI accepts quick overrides via `--backend-option key=value` (e.g., `--backend-option device=/dev/sg1` or `--backend-option size=2200x1650`).

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
