"""Scene that generates varied algorithmic art."""
from __future__ import annotations

import math
import random
from typing import Iterator

from PIL import ImageDraw

from ..core.renderer import blank
from ..core.scene import Frame, Scene
from ..core.generative import GenerativeAlgorithms

class GenerativeArtScene(Scene):
    def __init__(self, mode: str = "landscape") -> None:
        super().__init__(panel=None)
        self.mode = mode

    def frames(self) -> Iterator[Frame]:
        if self.panel is None:
            raise RuntimeError("Scene not bootstrapped with panel")

        canvas = blank((self.panel.width, self.panel.height))
        draw = ImageDraw.Draw(canvas)
        
        if self.mode == "landscape":
            # Generate a random function for the landscape
            freq = random.uniform(5.0, 15.0)
            phase = random.uniform(0.0, math.pi * 2)
            
            def terrain_func(x, z):
                # x and z are 0.0-1.0
                # Simple sine waves
                return (math.sin(x * freq + phase) * math.cos(z * freq)) * 0.5 + 0.5

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
            # We create a new image and paste it
            noise_img = GenerativeAlgorithms.jacquard_noise(
                self.panel.width, 
                self.panel.height, 
                warp_prob=0.9, 
                weft_prob=0.3
            )
            canvas.paste(noise_img, (0, 0))
            
            # Draw a label
            draw.text((20, self.panel.height - 40), "JACQUARD PROCESS No. 84", fill=0)

        yield canvas, {"hint": "full"}
