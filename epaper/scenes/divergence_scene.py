"""Scene visualizing the divergence score."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterator

from PIL import Image, ImageDraw, ImageFont

from ..core.renderer import blank
from ..core.scene import Frame, Scene


class DivergenceScene(Scene):
    def __init__(
        self,
        divergence_path: Path | str = Path("data/divergence.json"),
        font_path: str | None = None,
        title: str = "Divergence",
    ) -> None:
        super().__init__(panel=None)
        self.divergence_path = Path(divergence_path)
        self.font = ImageFont.truetype(font_path, 72) if font_path else ImageFont.load_default()
        self.small_font = ImageFont.truetype(font_path, 32) if font_path else ImageFont.load_default()
        self.title = title

    def frames(self) -> Iterator[Frame]:
        if self.panel is None:
            raise RuntimeError("Scene not bootstrapped with panel")
        data = self._load_data()
        canvas = blank((self.panel.width, self.panel.height))
        draw = ImageDraw.Draw(canvas)
        draw.text((40, 40), self.title, font=self.font, fill=0)
        score = data.get("score")
        level = (data.get("level") or "unknown").upper()
        draw.text((40, 150), f"Score: {score:.2f}" if score is not None else "Score: --", font=self.font, fill=0)
        draw.text((40, 240), f"Level: {level}", font=self.font, fill=0)
        bar_left = 40
        bar_top = 320
        bar_width = self.panel.width - 80
        bar_height = 50
        draw.rectangle((bar_left, bar_top, bar_left + bar_width, bar_top + bar_height), outline=0, width=3)
        if score is not None:
            pct = max(0.0, min(1.0, score / 5.0))
            fill_width = int(bar_width * pct)
            draw.rectangle((bar_left, bar_top, bar_left + fill_width, bar_top + bar_height), fill=0)
        metrics = data.get("metrics", {})
        y = bar_top + 100
        for name, info in metrics.items():
            text = f"{name}: {info.get('value', '--')} (z={info.get('z', '--')})"
            draw.text((40, y), text, font=self.small_font, fill=0)
            y += 50
        yield canvas, {"hint": "full"}

    def _load_data(self) -> Dict[str, float]:
        if not self.divergence_path.exists():
            return {}
        try:
            return json.loads(self.divergence_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
