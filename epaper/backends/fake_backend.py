"""Fake backend that writes frames to disk for development/testing."""
from __future__ import annotations

import itertools
import logging
import os
from pathlib import Path
from typing import Tuple

from PIL import Image

from . import Backend, PanelInfo

LOGGER = logging.getLogger(__name__)
_default_out_dir = Path("/tmp/epaper_frames")


class FakeBackend(Backend):
    """Backend that saves each frame as PNG for easy inspection."""

    def __init__(self, width: int = 1872, height: int = 1404, out_dir: Path | None = None, rotation: int = 0):
        self.width = width
        self.height = height
        self.out_dir = out_dir or _default_out_dir
        self._counter = itertools.count(1)
        self._panel = PanelInfo(width=width, height=height, rotation=rotation)

    def open(self) -> PanelInfo:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        LOGGER.info("FakeBackend writing frames to %s", self.out_dir)
        return self._panel

    def reset(self) -> None:  # pragma: no cover - nothing to do
        pass

    def _save(self, image: Image.Image, prefix: str) -> None:
        idx = next(self._counter)
        filename = self.out_dir / f"{idx:04d}_{prefix}.png"
        image.convert("L").save(filename)
        LOGGER.debug("Saved frame %s", filename)

    def draw_full(self, image: Image.Image, mode: str = "GC16") -> None:
        self._save(image, f"full_{mode}")

    def draw_partial(self, image: Image.Image, xy: Tuple[int, int] = (0, 0), mode: str = "DU") -> None:
        x, y = xy
        stamped = image.copy()
        self._save(stamped, f"partial_{mode}_{x}_{y}")

    def sleep(self) -> None:  # pragma: no cover - no hardware
        LOGGER.info("FakeBackend sleep (no-op)")

    def close(self) -> None:  # pragma: no cover - no hardware
        LOGGER.info("FakeBackend close (no-op)")
