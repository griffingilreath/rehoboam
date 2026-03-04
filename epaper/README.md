# epaper

> **DEPRECATED:** This package is the legacy e-ink display system. Active development has moved to [`visualizers/generative_eink/`](../visualizers/generative_eink/), which provides a config-driven, channel-based architecture. This package will be removed once `visualizers/generative_eink/` reaches feature parity. New scenes and backends should be added there, not here.

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

**Note**: The service runner supports standard flags like `--log-level` and `--data-dir`, consistent with other Jetson services.

## IT8951 Setup

If you need a cradle-to-grave guide for Raspberry Pi prep, driver compilation, udev rules, and hardware tuning, see [`docs/it8951_driver_playbook.md`](../docs/it8951_driver_playbook.md). The playbook covers Pi 3B+ vs 4/5 recommendations, SPI overlay tweaks, udev rules, and a migration checklist.

### SPI backend

1. Install the Python driver (`pip install it8951`). The backend wraps `AutoEPDDisplay` from the open-source driver published by Greg Meyer (see [`GregDMeyer/IT8951`](https://github.com/GregDMeyer/IT8951)).  
2. Wire the panel’s SPI pins to the Jetson/Pi per the Waveshare pinout (3.3V, GND, SCK, MOSI, MISO, CS, HRDY, RST).  
3. Run `python -m epaper.cli.main --backend spi --scene standby`. The driver auto-detects width/height from the panel.

### USB backend

1. Build the `it8951usb` helper from the official Waveshare sample repo (`git clone https://github.com/waveshare/IT8951 && make it8951usb`). Copy the binary into `bin/` or any location on `$PATH`.  
2. Plug the panel into USB (it shows up as `/dev/sg*`).  
3. Use `--backend usb` and override device/tool if needed: `python -m epaper.cli.main --backend usb --backend-option device=/dev/sg1 --backend-option tool=/opt/it8951usb`.

### Partial updates, higher refresh modes, and references

- **Waveforms in practice:** IT8951 exposes `DU` (fast monochrome partial), `GC16` (16-level grayscale full), plus `GL16/GLR16` ghost-reduction curves. Expect ≈150 ms partials for a 200×200 window in `DU` and ≈1 s for a full `GC16` refresh on the 7.5–7.8" glass based on Waveshare’s timing charts and Greg Meyer’s SPI driver benchmarks [^waveshare] [^greg].
- **Code pattern:** animate with partials, then clean up with a full refresh:

```python
from epaper.core.display import DisplayManager

manager = DisplayManager(backend="spi")
panel = manager.open()
frame = draw_scene(panel.width, panel.height)  # Pillow Image
manager.partial(frame, box=(120, 80, 480, 160), mode="DU")
# after several partials or every N seconds:
manager.full(frame, mode="GC16")
```

- **Higher refresh experiments:** tighten the bounding boxes (only repaint the Pi-hole card, divergence bar, or ticker) and stick to `DU` for “live” widgets. The USB backend can batch partials via `it8951usb --partial`, while the SPI backend benefits from raising the SPI clock to 12 MHz (configure via `backend_option spi_hz=12000000`).
- **More examples:** Waveshare’s repo shows partial-update command sequences and USB workflows; [`GregDMeyer/IT8951`](https://github.com/GregDMeyer/IT8951) includes rotation-aware SPI samples that informed `spi_backend.py`. The fake backend preserves rotation metadata so you can verify layouts before touching hardware.
- **Vendor sources:** clone the upstream repos under `third_party/it8951/` (see `third_party/README.md`) so the build scripts and patches stay versioned alongside the rest of the rack software.
- **Pi hardware tips:** A Pi 3B+ works for static scenes, but set `spi_hz=12_000_000`, keep partial regions <400×400 px, and disable the desktop compositor. Prefer a Pi 4 (or newer) for the semantic-channel visualizer so HA ingestion + rendering stay responsive.

[^waveshare]: Official [Waveshare IT8951 examples](https://github.com/waveshare/IT8951) document waveform codes, USB helpers, and refresh timing tables.
[^greg]: Greg Meyer’s [`IT8951` Python driver](https://github.com/GregDMeyer/IT8951) illustrates SPI wiring, fast waveform selection, and partial-refresh usage mirrored by this repo.

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

## Safe start/stop

- `python -m epaper.service.main --config epaper/config.yaml --shutdown` performs a final clean refresh and sleeps the panel; systemd uses this flag in `ExecStop` so accidental reboots don’t leave the glass mid-draw.
- When using systemd, `rehoboam-epaper.service` depends on `REHOBOAM_DATA`/`REHOBOAM_HOME`. Confirm `journalctl -u rehoboam-epaper` shows `Panel entering deep sleep` before cutting power.
- For manual testing, always end sessions with `--shutdown` (even on the fake backend) to mimic on-device behavior and prevent ghosting.

## Next steps

- Add additional scenes (Pi-hole live stats, divergence visualizer, generative art).
- Wire scene selection into `api_service` or a simple commander so you can switch modes without SSH.
- Optimize partial update regions for smoother animations once hardware is available.
