"""Command-line entrypoint for driving e-paper scenes."""
from __future__ import annotations

import argparse
import logging

from ..backends.fake_backend import FakeBackend
from ..backends.spi_backend import SPIBackend  # type: ignore  # optional dependency
from ..backends.usb_backend import USBBackend
from ..core.display import DisplayManager
from ..core import modes
from ..scenes import ActivityLogScene, DivergenceScene, PiHoleScene, StandbyScene

LOGGER = logging.getLogger(__name__)


def pick_backend(name: str):
    name = name.lower()
    if name == "fake":
        return FakeBackend()
    if name == "spi":
        return SPIBackend()
    if name == "usb":
        return USBBackend()
    raise SystemExit(f"Unknown backend '{name}'")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drive the Rehoboam e-paper scenes")
    parser.add_argument("--backend", default="fake", choices=["fake", "spi", "usb"], help="Which backend to use")
    parser.add_argument(
        "--scene",
        default="standby",
        choices=["standby", "activity_log", "pihole", "divergence"],
        help="Which scene to render",
    )
    parser.add_argument("--text", default="REHOBOAM", help="Text for standby scene")
    parser.add_argument("--font", help="Path to TTF font", default=None)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--shutdown", action="store_true", help="Only send standby to panel")
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    backend = pick_backend(args.backend)
    manager = DisplayManager(backend)

    if args.shutdown:
        LOGGER.info("Requesting shutdown/standby for e-paper panel")
        try:
            manager.start()
        except Exception:
            LOGGER.exception("Failed to start backend during shutdown")
        finally:
            manager.standby()
        return 0

    panel = manager.start()

    if args.scene == "standby":
        scene = StandbyScene(text=args.text, font_path=args.font)
    elif args.scene == "activity_log":
        scene = ActivityLogScene()
    elif args.scene == "pihole":
        scene = PiHoleScene()
    elif args.scene == "divergence":
        scene = DivergenceScene()
    else:  # pragma: no cover
        raise SystemExit(f"Scene '{args.scene}' not implemented")

    scene.bootstrap(panel)

    try:
        for frame, meta in scene.frames():
            hint = meta.get("hint")
            if hint == "partial":
                manager.partial(frame, xy=meta.get("xy", (0, 0)), mode=modes.PARTIAL_MODE)
            else:
                manager.full(frame, mode=modes.FULL_MODE)
    finally:
        manager.standby()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
