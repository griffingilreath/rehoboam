"""Config-driven runner for e-paper scenes."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import yaml

from ..backends.factory import create_backend
from ..core import modes
from ..core.display import DisplayManager
from ..scenes import ActivityLogScene, DivergenceScene, PiHoleScene, StandbyScene

SCENE_MAP = {
    "standby": StandbyScene,
    "activity_log": ActivityLogScene,
    "pihole": PiHoleScene,
    "divergence": DivergenceScene,
}


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run_scene(cfg: dict[str, Any]) -> None:
    backend_cfg = cfg.get("backend_config") or {}
    backend = create_backend(cfg.get("backend", "fake"), **backend_cfg)
    manager = DisplayManager(backend)
    panel = manager.start()
    try:
        scene_name = cfg.get("scene", "standby")
        factory = SCENE_MAP.get(scene_name)
        if not factory:
            raise SystemExit(f"Unknown scene '{scene_name}'")
        scene_kwargs = {k: v for k, v in cfg.items() if k not in {"backend", "scene", "log_level"}}
        scene = factory(**scene_kwargs)
        scene.bootstrap(panel)
        for frame, meta in scene.frames():
            if meta.get("hint") == "partial":
                manager.partial(frame, xy=meta.get("xy", (0, 0)), mode=modes.PARTIAL_MODE)
            else:
                manager.full(frame, mode=modes.FULL_MODE)
    finally:
        manager.standby()


def shutdown(cfg: dict[str, Any]) -> None:
    backend_cfg = cfg.get("backend_config") or {}
    backend = create_backend(cfg.get("backend", "fake"), **backend_cfg)
    manager = DisplayManager(backend)
    try:
        manager.start()
    except Exception:
        logging.exception("Failed to start backend for shutdown; proceeding anyway")
    finally:
        manager.standby()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run epaper scene from YAML config")
    parser.add_argument("--config", default="epaper/config.yaml")
    parser.add_argument("--shutdown", action="store_true", help="Only send standby command to the panel")
    args = parser.parse_args(argv)

    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    cfg = load_config(config_path)
    logging.basicConfig(level=getattr(logging, cfg.get("log_level", "INFO")))

    if args.shutdown:
        shutdown(cfg)
    else:
        run_scene(cfg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
