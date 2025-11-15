"""Display orchestration utilities."""
from __future__ import annotations

import logging
from typing import Tuple

from PIL import Image

from ..backends import Backend, PanelInfo
from . import modes

LOGGER = logging.getLogger(__name__)


class DisplayManager:
    """High-level controller that drives a backend with scenes."""

    def __init__(self, backend: Backend):
        self.backend = backend
        self.panel: PanelInfo | None = None

    def start(self) -> PanelInfo:
        LOGGER.info("Starting display backend %s", type(self.backend).__name__)
        panel = self.backend.open()
        self.backend.reset()
        self.panel = panel
        return panel

    def full(self, image: Image.Image, mode: str = modes.FULL_MODE) -> None:
        LOGGER.debug("Issuing full refresh (%s)", mode)
        self.backend.draw_full(image, mode=mode)

    def partial(
        self,
        image: Image.Image,
        xy: Tuple[int, int] = (0, 0),
        mode: str = modes.PARTIAL_MODE,
    ) -> None:
        LOGGER.debug("Issuing partial refresh at %s (%s)", xy, mode)
        self.backend.draw_partial(image, xy=xy, mode=mode)

    def standby(self) -> None:
        LOGGER.info("Putting display into standby")
        try:
            self.backend.sleep()
        finally:
            self.backend.close()
