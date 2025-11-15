"""Command-line entrypoint for driving e-paper scenes."""
from __future__ import annotations

import argparse
import logging

from ..backends.factory import create_backend
from ..core.display import DisplayManager
from ..core import modes
from ..scenes import ActivityLogScene, DivergenceScene, PiHoleScene, StandbyScene

LOGGER = logging.getLogger(__name__)


def parse_backend_options(items: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep:
            raise SystemExit(f"Invalid backend option '{item}'. Use key=value.")
        key = key.strip()
        value = value.strip()
        if key == "size" and "x" in value:
            try:
                w, h = value.lower().split("x", 1)
                result[key] = (int(w), int(h))
                continue
            except ValueError:
                raise SystemExit(f"Invalid size value '{value}'. Expected WIDTHxHEIGHT.")
        if value.isdigit():
            result[key] = int(value)
        else:
            result[key] = value
    return result


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
    parser.add_argument(
        "--backend-option",
        action="append",
        default=[],
        help="Override backend setting (key=value, e.g., device=/dev/sg1, size=1872x1404)",
    )
    parser.add_argument("--shutdown", action="store_true", help="Only send standby to panel")
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    backend_kwargs = parse_backend_options(args.backend_option)
    backend = create_backend(args.backend, **backend_kwargs)
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
