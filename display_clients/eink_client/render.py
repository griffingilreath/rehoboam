#!/usr/bin/env python3
"""Fetch canonical status and render a simple grayscale e-ink panel image."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List

import requests
from PIL import Image, ImageDraw, ImageFont

FONT_PATHS = [
    "/System/Library/Fonts/SFNS.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
DEFAULT_FONT_SIZE = 28
TITLE_FONT_SIZE = 40
CANVAS = (800, 480)  # typical Waveshare 7.5" panel


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fetch_json(url: str) -> Dict[str, Any]:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def summarize_leds(status: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for led in status.get("leds", [])[:10]:
        name = led.get("name") or f"LED {led.get('index', '?')}"
        health = (led.get("health") or "?").upper()
        act = led.get("activity_level") or 0
        lines.append(f"{name:<18} {health:<7} {act:>4.2f}")
    if len(status.get("leds", [])) > 10:
        lines.append("… (truncated)")
    return lines


def compose_image(status: Dict[str, Any], divergence: Dict[str, Any] | None) -> Image.Image:
    image = Image.new("L", CANVAS, color=255)
    draw = ImageDraw.Draw(image)
    title_font = load_font(TITLE_FONT_SIZE)
    body_font = load_font(DEFAULT_FONT_SIZE)

    timestamp = status.get("generated_at") or dt.datetime.utcnow().isoformat()
    timestamp_local = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone().strftime("%b %d %H:%M")

    draw.text((30, 20), "Rehoboam Rack", font=title_font, fill=0)
    draw.text((30, 80), f"Updated {timestamp_local}", font=body_font, fill=0)

    leds = summarize_leds(status)
    y = 140
    draw.text((30, 120), "LED Summary", font=body_font, fill=0)
    for line in leds:
        draw.text((40, y), line, font=body_font, fill=0)
        y += 32

    if divergence and "score" in divergence:
        draw.text((430, 120), "Divergence", font=body_font, fill=0)
        score = divergence.get("score", 0.0)
        level = divergence.get("level", "unknown").upper()
        draw.text((430, 160), f"Score: {score:.2f}", font=body_font, fill=0)
        draw.text((430, 200), f"Level: {level}", font=body_font, fill=0)

    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Rehoboam status for e-ink panels")
    parser.add_argument("--api", default="http://jetson-rack.local:8000", help="Base API URL")
    parser.add_argument("--output", default="output.png", help="Path to save the rendered image")
    args = parser.parse_args()

    status = fetch_json(f"{args.api}/status")
    try:
        divergence = fetch_json(f"{args.api}/divergence")
    except requests.RequestException:
        divergence = None

    image = compose_image(status, divergence)
    output_path = Path(args.output)
    image.save(output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
