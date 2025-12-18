"""Config-driven runner for e-paper scenes."""
from __future__ import annotations

import argparse
import logging
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml

from jetson.common.service_runner import RunnerOverrides, run_service
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
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

DEFAULT_CONFIG_PATH = "epaper/config.yaml"


@dataclass
class ServiceConfig:
    data_dir: Path
    backend: str
    backend_config: Dict[str, Any]
    scene: str
    log_level: str
    shutdown: bool = False
    scene_kwargs: Dict[str, Any] = field(default_factory=dict)


class EpaperService:
    def __init__(self, config: ServiceConfig):
        self._config = config
        self._backend = create_backend(config.backend, **config.backend_config)
        self._manager = DisplayManager(self._backend)
        self._stop_requested = False
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="epaper_service")

    def request_stop(self, *_: Any) -> None:
        logging.info("Stop requested; finishing current frame")
        self._stop_requested = True

    def run(self, run_once: bool = False) -> None:
        self._health.mark_running(self._identity)
        
        # If shutdown requested, just do that and exit
        if self._config.shutdown:
            self._do_shutdown()
            return

        # Normal run
        try:
            panel = self._manager.start()
            
            factory = SCENE_MAP.get(self._config.scene)
            if not factory:
                logging.error("Unknown scene '%s'", self._config.scene)
                self._health.mark_error(self._identity, f"unknown scene {self._config.scene}")
                return

            scene = factory(**self._config.scene_kwargs)
            scene.bootstrap(panel)
            
            for frame, meta in scene.frames():
                if self._stop_requested:
                    break

                if meta.get("hint") == "partial":
                    self._manager.partial(frame, xy=meta.get("xy", (0, 0)), mode=modes.PARTIAL_MODE)
                else:
                    self._manager.full(frame, mode=modes.FULL_MODE)
                
                self._health.mark_running(self._identity)
                
                if run_once:
                    break

        except Exception:
            logging.exception("E-paper service failed")
            self._health.mark_error(self._identity, "service failed")
            raise
        finally:
            self._manager.standby()

    def _do_shutdown(self) -> None:
        try:
            self._manager.start()
        except Exception:
            logging.warning("Failed to start backend for shutdown; forcing standby anyway")
        finally:
            self._manager.standby()
            logging.info("Panel placed in standby/shutdown")


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = overrides or RunnerOverrides()

    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    log_level = overrides.log_level or data.get("log_level", "INFO")
    
    # Extract scene kwargs (everything not reserved)
    reserved = {"backend", "backend_config", "scene", "log_level", "data_dir"}
    scene_kwargs = {k: v for k, v in data.items() if k not in reserved}

    return ServiceConfig(
        data_dir=data_dir,
        backend=data.get("backend", "fake"),
        backend_config=data.get("backend_config") or {},
        scene=data.get("scene", "standby"),
        log_level=log_level,
        scene_kwargs=scene_kwargs,
    )


def main() -> None:
    def _add_extra_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--shutdown",
            action="store_true",
            help="Only send standby command to the panel"
        )

    def _create_service(config: ServiceConfig, args: argparse.Namespace) -> EpaperService:
        if args.shutdown:
            config.shutdown = True
        logging.info("E-paper service starting (scene=%s, backend=%s)", config.scene, config.backend)
        return EpaperService(config)

    run_service(
        service_name="epaper_service",
        description="Drive e-paper scenes from config",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
        add_arguments=_add_extra_args,
    )


if __name__ == "__main__":
    main()
