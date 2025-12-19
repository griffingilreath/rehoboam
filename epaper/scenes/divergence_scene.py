"""Scene visualizing the divergence score using generative art techniques."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator

from PIL import ImageDraw, ImageFont

from ..core.renderer import blank
from ..core.scene import Frame, Scene
from ..core.generative import GenerativeAlgorithms

class DivergenceScene(Scene):
    def __init__(
        self,
        divergence_path: Path | str = Path("data/divergence.json"),
        font_path: str | None = None,
        title: str = "Divergence",
    ) -> None:
        super().__init__(panel=None)
        self.divergence_path = Path(divergence_path)
        self.font = ImageFont.truetype(font_path, 48) if font_path else ImageFont.load_default()
        self.large_font = ImageFont.truetype(font_path, 72) if font_path else ImageFont.load_default()
        self.title = title

    def frames(self) -> Iterator[Frame]:
        if self.panel is None:
            raise RuntimeError("Scene not bootstrapped with panel")
            
        data = self._load_data()
        score = data.get("score", 0.0) # Assume 0-10 or 0-1 range? Let's assume 0-100 or 0-1.
        # Normalize score to 0.0 - 1.0 for generative algos
        # Assuming score is like Z-score, maybe 0-5. Let's clamp.
        normalized_divergence = max(0.0, min(1.0, score / 5.0)) if score else 0.0
        
        canvas = blank((self.panel.width, self.panel.height))
        draw = ImageDraw.Draw(canvas)
        
        # Header
        draw.text((40, 30), self.title, font=self.large_font, fill=0)
        draw.text((40, 110), f"SCORE: {score:.2f}", font=self.font, fill=0)
        
        level = (data.get("level") or "NORMAL").upper()
        draw.text((40, 170), f"STATUS: {level}", font=self.font, fill=0)
        
        # Draw Schotter Grid in the bottom 2/3rds
        # Bounds: x=40, y=250, w=width-80, h=height-270
        bounds = (
            40, 
            250, 
            self.panel.width - 80, 
            self.panel.height - 290
        )
        
        # Rows/Cols depend on screen size, let's pick reasonable defaults
        # 12x12 grid is nice for Schotter
        GenerativeAlgorithms.schotter_grid(
            draw, 
            bounds, 
            rows=12, 
            cols=16, 
            divergence=normalized_divergence
        )
        
        # Add a border around the art area
        draw.rectangle(
            (bounds[0]-10, bounds[1]-10, bounds[0]+bounds[2]+10, bounds[1]+bounds[3]+10), 
            outline=0, 
            width=2
        )

        yield canvas, {"hint": "full"}

    def _load_data(self) -> dict[str, Any]:
        if not self.divergence_path.exists():
            return {"score": 0.0, "level": "UNKNOWN"}
        try:
            return json.loads(self.divergence_path.read_text(encoding="utf-8"))
        except Exception:
            return {"score": 0.0, "level": "ERROR"}
