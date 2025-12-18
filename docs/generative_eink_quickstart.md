# Generative E-Ink Quick Start

This guide walks through the fastest way to see the new config-driven visualizer running locally (fake backend) or on a Raspberry Pi with a Waveshare IT8951 e-paper panel.

## 1. Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r jetson/requirements.txt
pip install -r requirements-dev.txt
```

For Raspberry Pi hardware mode you also need the IT8951 driver stack; follow [`docs/it8951_driver_playbook.md`](it8951_driver_playbook.md) before continuing.

## 2. Run the Pi test driver (fake backend)

```bash
python -m visualizers.generative_eink.examples.pi_weight_demo --backend fake --interval 5
```

This loads the example `entities` + `channels` configs, feeds them synthetic sine/pulse waveforms, and saves grayscale PNG frames to `/tmp/epaper_frames`. Inspect these images to understand how the semantic channels map to bands/glyphs.

## 3. Run on hardware

Once the IT8951 SPI or USB backend is working:

```bash
# SPI HAT (GregDMeyer driver)
sudo python -m visualizers.generative_eink.examples.pi_weight_demo --backend spi --interval 10

# USB helper binary
sudo python -m visualizers.generative_eink.examples.pi_weight_demo --backend usb --interval 10
```

Flags you can tweak:

- `--entities`, `--channels`: point to your own YAML configs.
- `--font`: path to a local TTF for labels.
- `--width/--height`: override canvas size when using the fake backend.
- `--mode`: waveform (`GC16`, `DU`, etc.).

## 4. Next steps

- Read [`docs/generative_eink_visualizer_research.md`](generative_eink_visualizer_research.md) for channel semantics + historical influences.
- Use [`docs/generative_eink_visualizer_integration.md`](generative_eink_visualizer_integration.md) to wire the Home Assistant channel daemon and Pi renderer together.
- Follow the milestone checklist in [`docs/generative_eink_next_steps.md`](generative_eink_next_steps.md) as you implement the real data pipeline.
