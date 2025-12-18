#!/usr/bin/env python3
"""
Test driver for the generative e-ink visualizer running on a Raspberry Pi.

The script:
  * Loads the example entity/channel configs.
  * Uses synthetic waveforms to drive feature values (no Home Assistant needed).
  * Renders the resulting semantic channels into a simple grayscale composition.
  * Pushes the frames to an e-ink panel via the existing epaper backends.

Usage (Fake backend that saves PNGs to /tmp/epaper_frames):
    python -m visualizers.generative_eink.examples.pi_weight_demo --backend fake

Usage (Real IT8951 SPI HAT on Raspberry Pi):
    sudo python -m visualizers.generative_eink.examples.pi_weight_demo --backend spi

Dependencies for hardware mode:
    pip install pillow it8951
"""
from __future__ import annotations

import argparse
import itertools
import math
import signal
import sys
import time
from pathlib import Path
from typing import Callable, Dict

from PIL import Image, ImageDraw, ImageFont

from epaper.backends.factory import create_backend
from visualizers.generative_eink import VisualizerRuntime, config_loaders

DEFAULT_ENTITIES = (
    Path(__file__).resolve().parents[1] / "config" / "entities.example.yaml"
)
DEFAULT_CHANNELS = (
    Path(__file__).resolve().parents[1] / "config" / "channels.example.yaml"
)

CHANNEL_ORDER: tuple[str, ...] = (
    "house_activity",
    "soundscape",
    "daylight",
    "comfort",
    "resource_use",
    "network_health",
    "security_tension",
    "long_term_drift",
)


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def sine(period: float, *, amplitude: float = 0.5, offset: float = 0.5, phase: float = 0.0) -> Callable[[float], float]:
    def _fn(t: float) -> float:
        return clamp(offset + amplitude * math.sin((2 * math.pi * t / period) + phase))

    return _fn


def saw(period: float, *, offset: float = 0.0, amplitude: float = 1.0) -> Callable[[float], float]:
    def _fn(t: float) -> float:
        frac = ((t / period) + offset) % 1.0
        return clamp(offset + amplitude * frac)

    return _fn


def pulse(period: float, *, duty: float = 0.1, high: float = 1.0, low: float = 0.0, phase: float = 0.0) -> Callable[[float], float]:
    def _fn(t: float) -> float:
        frac = ((t + phase) % period) / period
        return high if frac < duty else low

    return _fn


FEATURE_DRIVERS: Dict[str, Callable[[float], float]] = {
    "motion_living_recent": sine(18, amplitude=0.45, offset=0.5),
    "media_is_playing": pulse(45, duty=0.4, high=1.0, low=0.0),
    "lights_on_ratio": sine(60, amplitude=0.35, offset=0.3, phase=0.4),
    "media_loudness": sine(30, amplitude=0.4, offset=0.5, phase=1.1),
    "blinds_open_ratio": sine(120, amplitude=0.5, offset=0.5),
    "outdoor_lux": sine(240, amplitude=0.5, offset=0.5),
    "daylight_trend": saw(600, offset=0.1, amplitude=0.8),
    "temp_deviation": sine(90, amplitude=0.3, offset=0.5, phase=0.3),
    "humidity_living": sine(75, amplitude=0.2, offset=0.45, phase=-0.2),
    "hvac_activity": pulse(50, duty=0.2, high=0.8, low=0.1),
    "water_flow_now": pulse(40, duty=0.15, high=1.0, low=0.0, phase=10),
    "water_today": saw(3600, offset=0.0, amplitude=0.6),
    "resource_trend": saw(7200, offset=0.1, amplitude=0.5),
    "clean_energy_score": sine(300, amplitude=0.4, offset=0.6),
    "net_load": sine(22, amplitude=0.4, offset=0.5, phase=0.5),
    "devices_online_ratio": sine(55, amplitude=0.25, offset=0.75),
    "net_latency": sine(27, amplitude=0.35, offset=0.4, phase=1.8),
    "front_door_locked": pulse(180, duty=0.1, high=1.0, low=0.0),
    "leak_alert": pulse(600, duty=0.02, high=1.0, low=0.0),
    "garage_open_recent": pulse(240, duty=0.08, high=1.0, low=0.0, phase=30),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loop channel weights on an e-ink panel.")
    parser.add_argument("--backend", default="fake", choices=("fake", "spi", "usb"), help="Which epaper backend to use.")
    parser.add_argument("--entities", default=str(DEFAULT_ENTITIES), help="Path to entities config.")
    parser.add_argument("--channels", default=str(DEFAULT_CHANNELS), help="Path to channels config.")
    parser.add_argument("--interval", type=float, default=8.0, help="Seconds between frames.")
    parser.add_argument("--mode", default="GC16", help="Waveform/mode passed to the backend.")
    parser.add_argument("--width", type=int, default=1872, help="Width override for fake backend.")
    parser.add_argument("--height", type=int, default=1404, help="Height override for fake backend.")
    parser.add_argument("--font", default=None, help="Optional path to a TTF font.")
    return parser.parse_args()


def load_font(font_path: str | None, size: int = 36) -> ImageFont.ImageFont:
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            print(f"Warning: could not load font {font_path}, falling back to default.", file=sys.stderr)
    return ImageFont.load_default()


def drive_features(runtime: VisualizerRuntime, t: float) -> None:
    for feature_id, fn in FEATURE_DRIVERS.items():
        runtime.set_feature(feature_id, fn(t))


def render_scene(width: int, height: int, channels: Dict[str, float], font: ImageFont.ImageFont) -> Image.Image:
    daylight = channels.get("daylight", 0.5)
    drift = channels.get("long_term_drift", 0.5)
    base = int(255 - (daylight * 90) - (drift * 60))
    image = Image.new("L", (width, height), color=base)
    draw = ImageDraw.Draw(image)

    # subtle vignette
    draw.rectangle((0, 0, width, height), outline=int(base - 20), width=8)

    margin = 80
    usable_height = height - (2 * margin)
    band_height = max(80, usable_height // len(CHANNEL_ORDER))

    for idx, channel in enumerate(CHANNEL_ORDER):
        value = float(channels.get(channel, 0.0))
        y0 = margin + idx * band_height
        y1 = min(y0 + band_height - 20, height - margin)
        x0 = margin
        x1 = width - margin
        fill_shade = int(255 - (value * 200))
        draw.rectangle((x0, y0, x1, y1), fill=int(base + 30), outline=fill_shade, width=3)

        bar_width = int((x1 - x0 - 40) * value)
        draw.rectangle((x0 + 20, y0 + 20, x0 + 20 + bar_width, y1 - 20), fill=fill_shade)

        label = f"{channel.replace('_', ' ').title()}   {value:0.2f}"
        draw.text((x0 + 30, y1 - 18), label, font=font, fill=0)

    # Event glyph for security tension
    sec = float(channels.get("security_tension", 0.0))
    glyph_size = 180
    glyph_x = width - margin - glyph_size
    glyph_y = margin - glyph_size // 2
    shade = int(255 - sec * 200)
    draw.ellipse((glyph_x, glyph_y, glyph_x + glyph_size, glyph_y + glyph_size), outline=shade, width=6)
    draw.text((glyph_x + 30, glyph_y + (glyph_size // 2) - 10), f"Tension {sec:0.2f}", font=font, fill=0)

    return image


def main() -> None:
    args = parse_args()
    entities_path = Path(args.entities)
    channels_path = Path(args.channels)

    if not entities_path.exists() or not channels_path.exists():
        raise SystemExit("Entities or channels config not found. Pass --entities/--channels.")

    config = config_loaders.load_config(entities_path, channels_path)
    runtime = VisualizerRuntime.from_config(config)

    backend_kwargs = {}
    if args.backend == "fake":
        backend_kwargs.update({"width": args.width, "height": args.height})

    backend = create_backend(args.backend, **backend_kwargs)
    panel = backend.open()
    font = load_font(args.font)

    running = True

    def _handle_sigint(signum: int, _frame) -> None:  # type: ignore[override]
        nonlocal running
        running = False
        print(f"Received signal {signum}, stopping loop...")

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)

    start = time.monotonic()
    frame_counter = itertools.count(1)

    try:
        while running:
            t = time.monotonic() - start
            drive_features(runtime, t)
            channels = runtime.get_channels()
            image = render_scene(panel.width, panel.height, channels, font)
            backend.draw_full(image, mode=args.mode)
            idx = next(frame_counter)
            print(f"[frame {idx:04d}] Channels: " + ", ".join(f"{k}={v:0.2f}" for k, v in channels.items()))
            time.sleep(args.interval)
    finally:
        backend.sleep()
        backend.close()


if __name__ == "__main__":
    main()
