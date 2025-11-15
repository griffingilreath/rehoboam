"""Scene that displays Pi-hole traffic stats."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterator

from PIL import Image, ImageDraw, ImageFont

from ..core.renderer import blank
from ..core.scene import Frame, Scene


class PiHoleScene(Scene):
    def __init__(
        self,
        raw_state_path: Path | str = Path("data/raw_state.json"),
        font_path: str | None = None,
        title: str = "Pi-hole Traffic",
    ) -> None:
        super().__init__(panel=None)
        self.raw_state_path = Path(raw_state_path)
        self.font = ImageFont.truetype(font_path, 42) if font_path else ImageFont.load_default()
        self.small_font = ImageFont.truetype(font_path, 32) if font_path else ImageFont.load_default()
        self.title = title

    def frames(self) -> Iterator[Frame]:
        if self.panel is None:
            raise RuntimeError("Scene not bootstrapped with panel")
        stats = self._load_stats()
        canvas = blank((self.panel.width, self.panel.height))
        draw = ImageDraw.Draw(canvas)
        draw.text((40, 30), self.title, font=self.font, fill=0)
        y = 110
        if not stats:
            draw.text((40, y), "No Pi-hole devices configured", font=self.small_font, fill=0)
        for entry in stats:
            draw.rectangle((30, y - 10, self.panel.width - 30, y + 90), outline=0, width=2)
            draw.text((50, y), entry["name"], font=self.font, fill=0)
            draw.text((50, y + 46), f"QPS {entry['qps']:.1f}", font=self.small_font, fill=0)
            draw.text((320, y + 46), f"Blocked {entry['blocked_ratio']*100:.1f}%", font=self.small_font, fill=0)
            status = entry.get("status") or "--"
            draw.text((600, y + 46), f"Status {status}", font=self.small_font, fill=0)
            y += 110
        yield canvas, {"hint": "full"}

    def _load_stats(self) -> list[Dict[str, float]]:
        if not self.raw_state_path.exists():
            return []
        try:
            payload = json.loads(self.raw_state_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        devices = payload.get("devices", {})
        stats = []
        for name, info in devices.items():
            if "qps" not in info and "blocked_ratio" not in info:
                continue
            stats.append(
                {
                    "name": name,
                    "qps": float(info.get("qps", 0.0)),
                    "blocked_ratio": float(info.get("blocked_ratio", 0.0)),
                    "status": info.get("pihole_status"),
                }
            )
        return stats
