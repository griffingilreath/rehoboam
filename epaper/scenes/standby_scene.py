"""Standby scene featuring a type-in and wipe animation."""
from __future__ import annotations

import itertools
from typing import Dict, Iterator

from PIL import Image, ImageChops, ImageFont

from ..backends import PanelInfo
from ..core.renderer import blank, draw_center_text, wipe_mask
from ..core.scene import Frame, Scene


class StandbyScene(Scene):
    def __init__(
        self,
        text: str = "REHOBOAM",
        font_path: str | None = None,
        point_size: int = 220,
        reveal_delay_steps: int = 6,
        wipe_steps: int = 12,
    ) -> None:
        super().__init__(panel=None)
        self.text = text
        self.font = (
            ImageFont.truetype(font_path, point_size)
            if font_path
            else ImageFont.load_default()
        )
        self.reveal_delay_steps = max(1, reveal_delay_steps)
        self.wipe_steps = max(4, wipe_steps)

    def bootstrap(self, panel: PanelInfo) -> None:
        self.panel = panel

    def frames(self) -> Iterator[Frame]:
        if self.panel is None:  # pragma: no cover - validated by caller
            raise RuntimeError("Scene not bootstrapped with panel")

        size = (self.panel.width, self.panel.height)
        base = blank(size)

        # 1) Type-in effect: reveal one character at a time
        for i in range(1, len(self.text) + 1):
            frame = base.copy()
            draw_center_text(frame, self.text[:i], self.font)
            for _ in range(self.reveal_delay_steps):
                yield frame.copy(), {"hint": "partial"}

        # 2) Left-to-right wipe erase
        final_text = blank(size)
        draw_center_text(final_text, self.text, self.font)
        white = blank(size, gray=255)
        for step in range(1, self.wipe_steps + 1):
            mask = wipe_mask(size, progress=step / self.wipe_steps)
            frame = Image.composite(white, final_text, mask)
            yield frame, {"hint": "partial"}

        # 3) Final crisp render
        crisp = blank(size)
        draw_center_text(crisp, self.text, self.font)
        yield crisp, {"hint": "full"}
