"""Backend factory helpers."""
from __future__ import annotations

from typing import Any

from . import Backend
from .fake_backend import FakeBackend
from .spi_backend import SPIBackend
from .usb_backend import USBBackend


def create_backend(name: str, **kwargs: Any) -> Backend:
    name = name.lower()
    if name == "fake":
        return FakeBackend(**kwargs)
    if name == "spi":
        return SPIBackend(**kwargs)
    if name == "usb":
        return USBBackend(**kwargs)
    raise ValueError(f"Unknown backend '{name}'")
