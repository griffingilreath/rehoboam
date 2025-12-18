# IT8951 Driver Playbook

Detailed guidance for preparing Raspberry Pi hardware, compiling the Waveshare IT8951 helpers, and running the Rehoboam e-paper stack without guesswork.

## Hardware Matrix & Recommendations

| Board | Status | Notes |
|-------|--------|-------|
| **Raspberry Pi 3B+** | *Supported with tuning* | Use only if you already have one attached to the panel. Limit partial refresh regions to ≤300×300 px, raise SPI clock to 12 MHz, and disable desktop/compositor services to free CPU. Expect ~1.1 s GC16 refreshes and ~180 ms DU partials. |
| **Raspberry Pi 4 (2 GB+)** | **Recommended** | Handles multiple services (HA listener + renderer) without throttling. Supports 20 MHz SPI clocks and USB 3.0 SSDs if you later offload HA snapshots. |
| **Raspberry Pi 5** | Future-friendly | Offers native PCIe, but the IT8951 HAT currently needs level shifting + new overlays. Only move here if you require extremely fast partial refresh support or HDMI mirroring. |

*Rule of thumb:* stay on Pi 3B+ for quick tests, deploy the long-lived visualizer stack on a Pi 4 or better to avoid CPU-bound rendering when HA event storms arrive.

## OS Prep (Pi OS Lite 64-bit)

1. Flash the latest Raspberry Pi OS Lite (64-bit) to a high-endurance microSD card.
2. Before first boot, create an empty `ssh` file on the boot partition and update `userconf` if you need a custom username/password.
3. Boot the Pi, SSH in, and run:
   ```bash
   sudo raspi-config nonint do_legacy 0      # enable Wayland-less console
   sudo raspi-config nonint do_i2c 0         # enable I2C (IT8951 HRDY pin uses it)
   sudo raspi-config nonint do_spi 0         # enable SPI for the HAT
   sudo raspi-config nonint do_expand_rootfs # optional but recommended
   ```
4. Append the following to `/boot/firmware/config.txt` (Bullseye/Bookworm) or `/boot/config.txt` (Legacy):
   ```ini
   dtoverlay=it8951,spi0-0,rotate=180
   dtparam=spi=on
   gpu_mem=32
   dtoverlay=disable-wifi      # optional, frees interrupts
   dtoverlay=disable-bt        # optional, frees UART if Teensy shares the tray
   ```
5. Reboot.

## Dependencies

```bash
sudo apt update
sudo apt install -y git build-essential libusb-1.0-0-dev libjpeg-dev python3-pip
```

> **Pi 3B+ tuning:** disable the desktop service (`sudo systemctl disable --now lightdm`) and enable performance governor (`echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`).

## Waveshare USB Helper

1. Clone the official repo under `third_party/it8951/waveshare` (path optional, but keeping it inside this repo avoids drift):
   ```bash
   git clone https://github.com/waveshare/IT8951 ~/it8951-waveshare
   cd ~/it8951-waveshare/it8951usb
   make it8951usb
   sudo install -m 755 it8951usb /usr/local/bin/it8951usb
   ```
2. Add a udev rule so non-root users can access `/dev/sg*`:
   ```bash
   sudo tee /etc/udev/rules.d/60-it8951.rules <<'EOF'
   SUBSYSTEM=="scsi_generic", ATTRS{model}=="IT8951", MODE="0664", GROUP="spi"
   EOF
   sudo groupadd -f spi && sudo usermod -aG spi $USER
   sudo udevadm control --reload && sudo udevadm trigger
   ```
3. Test:
   ```bash
   it8951usb /dev/sg0 0 0 100 100 < /dev/zero
   ```

## SPI Driver (GregDMeyer)

1. Clone and install directly from Git (not on PyPI):
   ```bash
   git clone https://github.com/GregDMeyer/IT8951 ~/IT8951-python
   cd ~/IT8951-python
   pip install .
   ```
2. Raise SPI bus speed if you use `spi_backend.py`:
   ```bash
   sudo tee -a /boot/firmware/config.txt <<'EOF'
   dtoverlay=spi0-1cs,cs0_pin=8,cs1_pin=7
   core_freq=500
   EOF
   ```
   The Greg driver exposes `AutoEPDDisplay(vcom=-2.30, spi_hz=12000000, rotate=0)`; pass these via `epaper/config.yaml` using `backend_config` once you wire up the backend options.

## Repository Integration Steps

1. From this repo root on the Pi:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r jetson/requirements.txt
   pip install -r requirements-dev.txt  # optional but keeps parity with CI
   ```
2. Populate `third_party/it8951/` (follow the README in that folder) or symlink the clones you already built.
3. Copy `epaper/config.example.yaml` → `epaper/config.yaml`, then edit:
   ```yaml
   backend: spi          # or usb
   backend_config:
     tool: /usr/local/bin/it8951usb   # USB mode only
     device: /dev/sg0                # USB mode only
     spi_hz: 12000000                # SPI mode only
     rotation: 180
   scene: standby
   data_dir: /opt/rehoboam/data
   ```
4. Sanity check using the fake backend before you touch hardware:
   ```bash
   python -m epaper.cli.main --backend fake --scene standby
   ```
5. Switch to SPI/USB once the panel is wired:
   ```bash
   sudo python -m epaper.cli.main --backend spi --scene activity_log
   # or
   sudo python -m epaper.cli.main --backend usb --scene divergence
   ```

## Performance Tips (Pi 3B+)

- **Partial refresh windows:** Keep them under 400×400 px in `DU` mode to avoid tearing. Batch updates by region (top metrics bar, mid-layer texture, alert glyphs).
- **Reduce ghosting:** After ~20 partials, schedule a GC16 refresh; the `DisplayManager` helper already exposes `full()` vs. `partial()` to do this.
- **CPU throttling:** Use a heat sink or set `force_turbo=1` with adequate cooling; otherwise the CPU drops to 600 MHz mid-refresh.
- **Power budget:** IT8951 boards can draw ~500 mA spikes over USB, so power the Pi from a stable 5 V/3 A supply (USB-C PD trigger boards work well for wall installs).

## Migration Guidance

- **Stay on Pi 3B+** if the panel only runs slow-changing compositions (activity log, once-hourly generative layers) and you already have the hardware installed.
- **Move to Pi 4** if you plan to stream semantic-channel-driven art, rotate between multiple scenes, or run Home Assistant event ingestion on the same box. The extra CPU headroom keeps partial refresh latency predictable.
- **Consider Pi 5/CM4** for future-proofing when you want to host the entire generative stack + HA proxies locally or experiment with two panels.

## Quick Integration Checklist

- [ ] SPI and/or USB helper installed and on `$PATH`
- [ ] `third_party/it8951/` populated with Waveshare + Greg repos (or documented symlink)
- [ ] `/etc/udev/rules.d/60-it8951.rules` applied for non-root access
- [ ] `epaper/config.yaml` configured with backend + options
- [ ] `python -m epaper.cli.main --backend fake` tested before hardware
- [ ] `visualizers/generative_eink/examples/pi_weight_demo.py` exercised with `--backend spi` to verify semantically-driven renders
- [ ] Systemd service (`rehoboam-epaper.service`) updated to point to the chosen backend and `--shutdown` flag for safe power-off

Refer back to this playbook whenever you change hardware or re-image the Pi; keeping everything documented avoids ghosting and mystery failures later.
