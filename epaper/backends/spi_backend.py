"""SPI backend using the official IT8951 Python library."""
from __future__ import annotations

import logging
from typing import Any, Tuple

from PIL import Image

try:
    from IT8951.display import AutoEPDDisplay  # type: ignore[import-not-found]
    from IT8951 import constants  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    AutoEPDDisplay = None
    constants = None

from . import Backend, PanelInfo

LOGGER = logging.getLogger(__name__)


class SPIBackend(Backend):
    """Thin wrapper around the IT8951 Python driver."""

    def __init__(self, **_: Any) -> None:
        if AutoEPDDisplay is None:
            raise RuntimeError(
                "IT8951 library not installed. Install `it8951` to use SPIBackend."
            )
        self._display: AutoEPDDisplay | None = None
        self._panel: PanelInfo | None = None

    def open(self) -> PanelInfo:
        LOGGER.info("Initializing SPI e-paper display via IT8951 Python lib")
        self._display = AutoEPDDisplay()
        panel = PanelInfo(width=self._display.width, height=self._display.height)
        self._panel = panel
        return panel

    def reset(self) -> None:  # pragma: no cover - library handles internally
        pass

    def _ensure_display(self) -> AutoEPDDisplay:
        if self._display is None:
            raise RuntimeError("SPIBackend not opened")
        return self._display

    def draw_full(self, image: Image.Image, mode: str = "GC16") -> None:
        disp = self._ensure_display()
        disp.frame_buf.paste(image.convert("L"))
        waveform = getattr(constants.DisplayModes, mode, constants.DisplayModes.GC16)
        disp.draw_full(waveform)

    def draw_partial(
        self,
        image: Image.Image,
        xy: Tuple[int, int] = (0, 0),
        mode: str = "DU",
    ) -> None:
        """Attempt a partial update using the IT8951 library."""
        disp = self._ensure_display()
        
        # Paste the partial image into the framebuffer at the correct offset
        disp.frame_buf.paste(image.convert("L"), xy)
        
        # Resolve waveform mode (DU is typical for partial updates)
        waveform = getattr(constants.DisplayModes, mode, constants.DisplayModes.DU)
        
        LOGGER.debug("SPI partial update at %s with mode %s", xy, mode)
        
        # IT8951 library supports draw_partial using the internal frame_buf
        # It updates only the changed region if possible, or falls back to optimized full.
        try:
            disp.draw_partial(waveform)
        except AttributeError:
            # Fallback for older library versions that might lack explicit partial
            disp.draw_full(waveform)

    def sleep(self) -> None:
        if self._display is None:  # pragma: no cover
            return
        try:
            self._display.epd.sleep()
            LOGGER.info("SPI display put to sleep")
        except Exception:  # pragma: no cover - optional
            LOGGER.exception("Failed to sleep SPI display")

    def close(self) -> None:
        self._display = None
        LOGGER.info("SPI display closed")
