# third_party/it8951

Reference snapshot location for IT8951 tooling and drivers used by the e-paper stack. See [`docs/it8951_driver_playbook.md`](../../docs/it8951_driver_playbook.md) for a full Pi setup guide; this README focuses on how to populate the `third_party` tree so the repo stays self-contained.

## Suggested layout

```
third_party/it8951/
├── waveshare/      # Official USB/SPI samples, it8951usb binary
├── gregdmeyer/     # Python AutoEPDDisplay driver
└── patches/        # Optional local patches (keep diff files, not edited sources)
```

Nothing is checked in by default to keep the repo lean. Populate the tree locally with either git submodules or one-off clones:

```bash
# Official Waveshare samples (C, USB helper)
git submodule add https://github.com/waveshare/IT8951 third_party/it8951/waveshare

# Greg Meyer's Python driver (used by spi_backend.py)
git submodule add https://github.com/GregDMeyer/IT8951 third_party/it8951/gregdmeyer
```

After cloning, build the USB helper so `epaper/backends/usb_backend.py` can invoke it:

```bash
cd third_party/it8951/waveshare/it8951usb
make it8951usb
cp it8951usb ../../../bin/it8951usb
```

Document any local tweaks by adding patch files under `patches/` (e.g., `0001-Reduce-default-refresh.patch`) and referencing them from the relevant README so they can be re-applied after upstream updates.

## Why keep this here?

- Makes it obvious which code is upstream vs. maintained by this repo.
- Keeps firmware/e-paper history clean while still providing a canonical place to store licensed dependencies.
- Encourages periodic updates (update the submodule pointer or re-clone) instead of editing vendored code in place.

## Quick install snippets

```bash
# Build + install USB helper
cd third_party/it8951/waveshare/it8951usb
make it8951usb
install -m 755 it8951usb ../../../../bin/it8951usb

# Install the Python SPI driver directly from source
pip install third_party/it8951/gregdmeyer
```

> The Greg Meyer driver is not published on PyPI; installing from the local clone keeps CI happy and lets you patch it if needed.

