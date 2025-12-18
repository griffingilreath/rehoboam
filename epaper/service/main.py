"""Config-driven runner for e-paper scenes."""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

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

DEFAULT_CONFIG_PATH = str(Path(__file__).parent.parent / "config.yaml")


@dataclass
class ServiceConfig:
    data_dir: Path
    backend: str
    backend_config: Dict[str, Any]
    scene: str
    log_level: str
    extra_config: Dict[str, Any] = field(default_factory=dict)


class EpaperService:
    def __init__(self, config: ServiceConfig, shutdown_mode: bool = False) -> None:
        self._config = config
        self._shutdown_mode = shutdown_mode
        self._stop_requested = False

    def request_stop(self, *_: Any) -> None:
        logging.info("Stop requested")
        self._stop_requested = True

    def run(self, run_once: bool = False) -> None:
        """
        Run the scene.

        Args:
            run_once: Ignored; this service currently always runs a single pass.
        """
        if self._shutdown_mode:
            self._do_shutdown()
            return

        self._run_scene()

    def _do_shutdown(self) -> None:
        logging.info("Shutting down display...")
        backend = create_backend(self._config.backend, **self._config.backend_config)
        manager = DisplayManager(backend)
        try:
            manager.start()
        except Exception:
            logging.exception("Failed to start backend for shutdown; proceeding anyway")
        finally:
            manager.standby()

    def _run_scene(self) -> None:
        backend = create_backend(self._config.backend, **self._config.backend_config)
        manager = DisplayManager(backend)
        panel = manager.start()
        try:
            scene_name = self._config.scene
            factory = SCENE_MAP.get(scene_name)
            if not factory:
                logging.error("Unknown scene '%s'", scene_name)
                return

            scene = factory(**self._config.extra_config)
            scene.bootstrap(panel)
            
            for frame, meta in scene.frames():
                if self._stop_requested:
                    break
                
                if meta.get("hint") == "partial":
                    manager.partial(frame, xy=meta.get("xy", (0, 0)), mode=modes.PARTIAL_MODE)
                else:
                    manager.full(frame, mode=modes.FULL_MODE)
        finally:
            manager.standby()


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = overrides or RunnerOverrides()
    
    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    log_level = overrides.log_level or data.get("log_level", "INFO")
    
    # Extract known fields, leave the rest for the scene
    known_keys = {"backend", "backend_config", "scene", "log_level", "data_dir"}
    extra_config = {k: v for k, v in data.items() if k not in known_keys}

    return ServiceConfig(
        data_dir=data_dir,
        backend=data.get("backend", "fake"),
        backend_config=data.get("backend_config") or {},
        scene=data.get("scene", "standby"),
        log_level=log_level,
        extra_config=extra_config,
    )


def main() -> None:
    def _add_extra_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--shutdown", 
            action="store_true", 
            help="Only send standby command to the panel"
        )

    def _create_service(config: ServiceConfig, args: argparse.Namespace) -> EpaperService:
        logging.info("E-paper service using backend '%s' and scene '%s'", config.backend, config.scene)
        return EpaperService(config, shutdown_mode=args.shutdown)

    run_service(
        service_name="epaper_service",
        description="Run epaper scene from YAML config",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
        add_arguments=_add_extra_args,
        supports_once=False,
        supports_interval_override=False,
    )


if __name__ == "__main__":
    main()
