# Generative E-Ink Visualizer (Scaffold)

This package isolates the next-generation, config-driven e-ink visualizer so it can evolve independently from the legacy epaper scenes. It mirrors the research captured in `docs/generative_eink_visualizer_research.md` and the accompanying technical plan PDFs.

## Objectives

- Treat Home Assistant as the canonical source for all device telemetry.
- Normalize raw entities into a reusable feature space defined entirely by config.
- Compress features into ~8 semantic channels that the artwork understands.
- Keep the rendering layer agnostic: it only consumes semantic channels.
- Make new entities/channels a config change, not a code change, whenever possible.

## Repository Layout

```
visualizers/
  generative_eink/
    README.md                 # You are here
    __init__.py               # Package export surface
    types.py                  # Shared dataclasses for HA-style events
    config/
      models.py               # Config dataclasses + helpers
      loaders.py              # YAML/JSON loading utilities
      entities.example.yaml   # Sample Home Assistant entity-to-feature mapping
      channels.example.yaml   # Sample semantic channel formulas
    feature_space.py          # Maintains normalized feature dictionary
    channel_space.py          # Evaluates semantic channels from features
    runtime.py                # High-level coordinator + public API
```

## Step-by-Step Build Plan

1. **Wire Home Assistant ingestion**
   - Implement a lightweight subscriber (WebSocket or long-poll) that converts HA events into `EntityStateEvent` instances.
   - Reuse the `FeatureSpace` API to update features as events arrive.

2. **Prototype feature extraction offline**
   - Use recorded HA event logs (JSON) to feed `FeatureSpace` and validate normalization/smoothing parameters.
   - Extend `entities.example.yaml` until it covers the initial sensor list.

3. **Validate semantic channels**
   - Author the first version of `channels.yaml`, run it through `ChannelSpace`, and visualize channel traces over time.
   - Adjust weights/curves until each channel stays within a predictable range.

4. **Design rendering contracts**
   - Define a `ChannelPayload` schema (likely JSON) that the Mac-based art runtime and the Waveshare driver both understand.
   - Prototype a simulator window that renders grayscale scenes using the channel payload.

5. **Implement Waveshare driver hookup**
   - Decide whether to push pre-rendered bitmaps or to run a lightweight renderer on the Pi.
   - Use the `VisualizerRuntime` facade to produce channel updates and trigger partial refreshes.

6. **Add regression harnesses**
   - Store golden HA event snippets + expected channel outputs to guard against future refactors.
   - Include smoke tests that load both example configs to ensure they stay schema-compliant.

As these steps progress, keep the legacy `epaper` module untouched so existing deployments remain stable.

## Raspberry Pi Test Loop

To see the semantic channels animate on real hardware (or just save PNGs), use the included test driver:

```bash
# Fake backend that writes frames to /tmp/epaper_frames
python -m visualizers.generative_eink.examples.pi_weight_demo --backend fake

# On a Pi with the Waveshare IT8951 SPI HAT + it8951 Python lib
sudo python -m visualizers.generative_eink.examples.pi_weight_demo --backend spi

# If you use the USB helper binary from epaper/backends/usb_backend.py
sudo python -m visualizers.generative_eink.examples.pi_weight_demo --backend usb
```

The script loads the example entity/channel configs, feeds them with synthetic sine/pulse waveforms, renders a simple grayscale composition, and pushes frames through the existing epaper backends. Hardware mode requires `pip install pillow it8951` plus the appropriate driver binaries (see `third_party/it8951/README.md`).
