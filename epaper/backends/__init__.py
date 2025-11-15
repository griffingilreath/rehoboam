"""Backend interfaces for driving e-paper displays."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Tuple

from PIL import Image


@dataclass
class PanelInfo:
    """Metadata about the connected e-paper panel."""

    width: int
    height: int
    rotation: int = 0


class Backend(Protocol):
    """Adapter that knows how to talk to a physical (or fake) panel."""

    def open(self) -> PanelInfo:
        """Initialize hardware and return panel metadata."""

    def reset(self) -> None:
        """Reset or wake the panel if needed."""

    def draw_full(self, image: Image.Image, mode: str = "GC16") -> None:
        """Draw a full-frame image using the requested waveform/mode."""

    def draw_partial(
        self,
        image: Image.Image,
        xy: Tuple[int, int] = (0, 0),
        mode: str = "DU",
    ) -> None:
        """Draw a partial update at the specified top-left coordinate."""

    def sleep(self) -> None:
        """Put the panel into low-power standby."""

    def close(self) -> None:
        """Release any resources (SPI handles, subprocesses, etc.)."""
