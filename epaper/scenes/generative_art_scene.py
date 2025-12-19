"""Scene that generates varied algorithmic art based on channel data."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, Iterator, List

from PIL import Image, ImageDraw, ImageFont

from ..core.scene import Frame, Scene

LOGGER = logging.getLogger(__name__)

CHANNEL_ORDER = (
    "house_activity",
    "soundscape",
    "daylight",
    "comfort",
    "resource_use",
    "network_health",
    "security_tension",
    "long_term_drift",
)

class GenerativeArtScene(Scene):
    def __init__(
        self, 
        mode: str = "landscape",
        channels_path: Path | str = Path("data/generative_channels.json"),
        font_path: str | None = None
    ) -> None:
        super().__init__(panel=None)
        self.mode = mode
        self.channels_path = Path(channels_path)
        self.font = ImageFont.truetype(font_path, 36) if font_path else ImageFont.load_default()
        self.last_full_refresh = 0.0
        # Configurable interval for checking updates
        self.interval = 30.0 
        # Full refresh every hour
        self.full_refresh_interval = 3600.0

    def frames(self) -> Iterator[Frame]:
        if self.panel is None:
            raise RuntimeError("Scene not bootstrapped with panel")

        while True:
            channels = self._read_channels()
            canvas = self._render_scene(channels)
            
            now = time.time()
            hint = "partial"
            
            # Force full refresh periodically
            if now - self.last_full_refresh > self.full_refresh_interval:
                hint = "full"
                self.last_full_refresh = now
                
            yield canvas, {"hint": hint, "xy": (0, 0)}
            
            time.sleep(self.interval)

    def _read_channels(self) -> Dict[str, float]:
        if not self.channels_path.exists():
            LOGGER.warning(f"Channels file not found at {self.channels_path}")
            return {}
        try:
            return json.loads(self.channels_path.read_text(encoding="utf-8"))
        except Exception:
            LOGGER.exception("Failed to read channels file")
            return {}

    def _render_scene(self, channels: Dict[str, float]) -> Image.Image:
        width = self.panel.width
        height = self.panel.height
        
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
            draw.text((x0 + 30, y1 - 18), label, font=self.font, fill=0)

        # Event glyph for security tension
        sec = float(channels.get("security_tension", 0.0))
        glyph_size = 180
        glyph_x = width - margin - glyph_size
        glyph_y = margin - glyph_size // 2
        shade = int(255 - sec * 200)
        draw.ellipse((glyph_x, glyph_y, glyph_x + glyph_size, glyph_y + glyph_size), outline=shade, width=6)
        draw.text((glyph_x + 30, glyph_y + (glyph_size // 2) - 10), f"Tension {sec:0.2f}", font=self.font, fill=0)

        return image
