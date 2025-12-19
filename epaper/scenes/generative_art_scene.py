"""Scene that generates varied algorithmic art."""
from __future__ import annotations

import math
import random
import json
from pathlib import Path
from typing import Iterator

from PIL import ImageDraw

from ..core.renderer import blank
from ..core.scene import Frame, Scene
from ..core.generative import GenerativeAlgorithms

class GenerativeArtScene(Scene):
    def __init__(self, mode: str = "landscape") -> None:
        super().__init__(panel=None)
        self.mode = mode

    def _read_channels(self) -> dict:
        try:
            # TODO: make this path configurable
            path = Path("data/generative_channels.json")
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def frames(self) -> Iterator[Frame]:
        if self.panel is None:
            raise RuntimeError("Scene not bootstrapped with panel")

        channels = self._read_channels()
        # Default values if file missing
        activity = channels.get("house_activity", 0.5)
        daylight = channels.get("daylight", 0.5)
        drift = channels.get("long_term_drift", 0.0)

        canvas = blank((self.panel.width, self.panel.height))
        draw = ImageDraw.Draw(canvas)
        
        if self.mode == "landscape":
            # Generate a random function for the landscape
            # Use drift to influence seed or phase
            freq = 5.0 + (activity * 15.0) # More activity = higher frequency
            phase = drift * math.pi * 2
            
            def terrain_func(x, z):
                # x and z are 0.0-1.0
                # Simple sine waves
                val = (math.sin(x * freq + phase) * math.cos(z * freq)) * 0.5 + 0.5
                # Daylight controls "water level" or fill
                if val < (1.0 - daylight):
                     return 0.0
                return val

            bounds = (0, 0, self.panel.width, self.panel.height)
            GenerativeAlgorithms.floating_horizon(
                draw, 
                bounds, 
                terrain_func, 
                steps=80, 
                z_depths=40
            )
            
        elif self.mode == "fabric":
            # Jacquard Noise
            # Activity controls warp probability (chaos)
            # Daylight controls weft (density)
            noise_img = GenerativeAlgorithms.jacquard_noise(
                self.panel.width, 
                self.panel.height, 
                warp_prob=0.5 + (activity * 0.4), 
                weft_prob=0.2 + (daylight * 0.6)
            )
            canvas.paste(noise_img, (0, 0))
            
            # Draw a label
            draw.text((20, self.panel.height - 40), f"JACQUARD PROCESS | Drift {drift:.2f}", fill=0)

        yield canvas, {"hint": "full"}
