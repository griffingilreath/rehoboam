"""Config-driven runner for e-paper scenes."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import yaml

from jetson.common.service_runner import RunnerOverrides, run_service
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


class EpaperService:
    def __init__(self, config: dict[str, Any], args: argparse.Namespace):
        self._config = config
        self._args = args
        self._stop_requested = False
        
        backend_cfg = config.get("backend_config") or {}
        backend = create_backend(config.get("backend", "fake"), **backend_cfg)
        self._manager = DisplayManager(backend)

    def request_stop(self, *_: Any) -> None:
        self._stop_requested = True

    def run(self, run_once: bool = False) -> None:
        if getattr(self._args, "shutdown", False):
            self._shutdown_panel()
            return

        self._manager.start()
        try:
            self._run_scene()
        finally:
            self._manager.standby()

    def _shutdown_panel(self) -> None:
        try:
            self._manager.start()
        except Exception:
            logging.exception("Failed to start backend for shutdown; proceeding anyway")
        finally:
            self._manager.standby()

    def _run_scene(self) -> None:
        panel = self._manager.start()
        scene_name = self._config.get("scene", "standby")
        factory = SCENE_MAP.get(scene_name)
        if not factory:
            logging.error("Unknown scene '%s'", scene_name)
            return

        # Filter out config keys that aren't for the scene
        scene_kwargs = {
            k: v for k, v in self._config.items() 
            if k not in {"backend", "scene", "log_level", "backend_config"}
        }
        scene = factory(**scene_kwargs)
        scene.bootstrap(panel)
        
        for frame, meta in scene.frames():
            if self._stop_requested:
                break
            
            if meta.get("hint") == "partial":
                self._manager.partial(frame, xy=meta.get("xy", (0, 0)), mode=modes.PARTIAL_MODE)
            else:
                self._manager.full(frame, mode=modes.FULL_MODE)


def load_config(path: Path, overrides: RunnerOverrides) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # We could implement env expansion here if needed, similar to jetson services
    return data


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--shutdown", action="store_true", help="Only send standby command to the panel")


def main() -> None:
    run_service(
        service_name="epaper_service",
        description="Run epaper scene from YAML config",
        default_config_path="epaper/config.yaml",
        load_config=load_config,
        create_service=EpaperService,
        add_arguments=add_arguments,
    )


if __name__ == "__main__":
    main()
