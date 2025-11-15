"""Scene abstraction for reusable animations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, Tuple

from PIL import Image

from ..backends import PanelInfo

Frame = Tuple[Image.Image, Dict[str, object]]


@dataclass
class Scene:
    """Base class for orchestrating a sequence of frames."""

    panel: PanelInfo | None = None

    def bootstrap(self, panel: PanelInfo) -> None:
        self.panel = panel

    def frames(self) -> Iterator[Frame]:  # pragma: no cover - interface
        raise NotImplementedError
