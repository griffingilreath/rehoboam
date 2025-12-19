"""USB backend that streams frames to the it8951usb helper binary."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

from PIL import Image

from . import Backend, PanelInfo

LOGGER = logging.getLogger(__name__)


class USBBackend(Backend):
    """Backend that pipes raw grayscale data to the external it8951usb tool."""

    def __init__(
        self,
        device: str = "/dev/sg0",
        tool: str = "it8951usb",
        size: Tuple[int, int] = (1872, 1404),
    ) -> None:
        self.device = device
        self.tool_path = shutil.which(tool) or str(Path("bin") / tool)
        self.size = size
        self._panel = PanelInfo(width=size[0], height=size[1])

    def open(self) -> PanelInfo:
        if not Path(self.tool_path).exists():
            raise RuntimeError(
                f"USB backend helper '{self.tool_path}' not found. Build it8951usb first."
            )
        LOGGER.info("USB backend using %s", self.tool_path)
        return self._panel

    def reset(self) -> None:  # pragma: no cover - tool handles implicitly
        pass

    def _pipe(self, image: Image.Image, x: int, y: int, w: int, h: int) -> None:
        cmd = [self.tool_path, self.device, str(x), str(y), str(w), str(h)]
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        buf = image.convert("L").tobytes()
        assert proc.stdin is not None
        try:
            out, err = proc.communicate(input=buf, timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise RuntimeError(f"USB backend timed out after 10s: {cmd}")

        if proc.returncode != 0:
            err_msg = err.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"USB backend failed (code {proc.returncode}): {err_msg} CMD: {cmd}"
            )
        LOGGER.debug("USB backend wrote %s bytes via %s", len(buf), cmd)

    def draw_full(self, image: Image.Image, mode: str = "GC16") -> None:
        w, h = self.size
        self._pipe(image, 0, 0, w, h)

    def draw_partial(
        self,
        image: Image.Image,
        xy: Tuple[int, int] = (0, 0),
        mode: str = "DU",
    ) -> None:
        x, y = xy
        w, h = image.size
        self._pipe(image, x, y, w, h)

    def sleep(self) -> None:  # pragma: no cover
        LOGGER.info("USB backend sleep (no-op)")

    def close(self) -> None:  # pragma: no cover
        LOGGER.info("USB backend close (no-op)")
