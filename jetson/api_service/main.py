#!/usr/bin/env python3
"""Expose canonical LED state via FastAPI."""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


DEFAULT_CONFIG_PATH = "jetson/api_service/config.yaml"
DEFAULT_LED_CONFIG_FILENAME = "led_config.json"
DEFAULT_CANONICAL_FILENAME = "canonical_state.json"
DEFAULT_HISTORY_FILENAME = "history.json"
DEFAULT_HEALTH_FILENAME = "service_health.json"
DEFAULT_DIVERGENCE_FILENAME = "divergence.json"


@dataclass
class ServiceConfig:
    data_dir: Path
    led_config_filename: str = DEFAULT_LED_CONFIG_FILENAME
    canonical_state_filename: str = DEFAULT_CANONICAL_FILENAME
    history_filename: str = DEFAULT_HISTORY_FILENAME
    health_filename: str = DEFAULT_HEALTH_FILENAME
    divergence_filename: str = DEFAULT_DIVERGENCE_FILENAME
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    cors_origins: list[str] = field(default_factory=list)
    cache_ttl_seconds: float = 0.5
    log_level: str = "INFO"

    @property
    def led_config_path(self) -> Path:
        return self.data_dir / self.led_config_filename

    @property
    def canonical_path(self) -> Path:
        return self.data_dir / self.canonical_state_filename

    @property
    def history_path(self) -> Path:
        return self.data_dir / self.history_filename

    @property
    def health_path(self) -> Path:
        return self.data_dir / self.health_filename

    @property
    def divergence_path(self) -> Path:
        return self.data_dir / self.divergence_filename


class JsonFileCache:
    """Tiny cache around JSON files with TTL + mtime validation."""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = max(0.0, ttl_seconds)
        self._cache: Dict[Path, tuple[float, float, Any]] = {}

    def read(self, path: Path, allow_empty: bool = False) -> Optional[Any]:
        if not path.exists():
            return {} if allow_empty else None
        now = time.monotonic()
        cached = self._cache.get(path)
        mtime = path.stat().st_mtime
        if cached and now < cached[0] and cached[1] == mtime:
            return cached[2]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging.error("Invalid JSON in %s: %s", path, exc)
            return None
        expires = now + self._ttl if self._ttl else now
        self._cache[path] = (expires, mtime, data)
        return data


def create_app(config: ServiceConfig) -> FastAPI:
    cache = JsonFileCache(config.cache_ttl_seconds)
    app = FastAPI(title="Rehoboam API", version="1.0.0")

    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/status", summary="Current canonical LED state")
    def get_status() -> Dict[str, Any]:
        data = cache.read(config.canonical_path)
        if data is None:
            raise HTTPException(status_code=503, detail="Canonical state not available yet")
        return data

    @app.get("/config", summary="Current LED configuration")
    def get_config() -> Dict[str, Any]:
        data = cache.read(config.led_config_path)
        if data is None:
            raise HTTPException(status_code=503, detail="LED config not available yet")
        return data

    @app.get("/history", summary="Recent canonical state history")
    def get_history() -> Dict[str, Any]:
        data = cache.read(config.history_path, allow_empty=True)
        return data or {"entries": []}

    @app.get("/health", summary="Reported health of Jetson services")
    def get_health() -> Dict[str, Any]:
        data = cache.read(config.health_path, allow_empty=True)
        if not data:
            return {"status": "unknown", "services": []}
        return data

    @app.get("/info", summary="API metadata")
    def get_info() -> Dict[str, Any]:
        return {
            "app": app.title,
            "version": app.version,
            "files": {
                "canonical_state": str(config.canonical_path),
                "led_config": str(config.led_config_path),
                "history": str(config.history_path),
                "divergence": str(config.divergence_path),
            },
        }

    @app.get("/divergence", summary="Latest divergence / anomaly score")
    def get_divergence() -> Dict[str, Any]:
        data = cache.read(config.divergence_path, allow_empty=True)
        if not data:
            raise HTTPException(status_code=404, detail="Divergence data not available")
        return data

    return app


def load_service_config(path: Path) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ServiceConfig(
        data_dir=Path(data.get("data_dir", "./data")).expanduser().resolve(),
        led_config_filename=data.get("led_config_filename", DEFAULT_LED_CONFIG_FILENAME),
        canonical_state_filename=data.get("canonical_state_filename", DEFAULT_CANONICAL_FILENAME),
        history_filename=data.get("history_filename", DEFAULT_HISTORY_FILENAME),
        health_filename=data.get("health_filename", DEFAULT_HEALTH_FILENAME),
        host=data.get("host", "0.0.0.0"),
        port=int(data.get("port", 8000)),
        reload=bool(data.get("reload", False)),
        cors_origins=data.get("cors_origins", []),
        cache_ttl_seconds=float(data.get("cache_ttl_seconds", 0.5)),
        divergence_filename=data.get("divergence_filename", DEFAULT_DIVERGENCE_FILENAME),
        log_level=(data.get("logging", {}) or {}).get("level", "INFO"),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve canonical LED data via HTTP")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--host",
        help="Override host binding",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Override port",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable FastAPI autoreload (dev only)",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Override configured log level",
    )
    return parser.parse_args()


def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    service_config = load_service_config(config_path)
    log_level = args.log_level or service_config.log_level
    configure_logging(log_level)

    host = args.host or service_config.host
    port = args.port or service_config.port
    reload_flag = args.reload or service_config.reload

    app = create_app(service_config)

    logging.info("Starting api_service on %s:%s", host, port)

    uvicorn_config = uvicorn.Config(
        app,
        host=host,
        port=port,
        reload=reload_flag,
        log_level=log_level.lower(),
    )
    server = uvicorn.Server(uvicorn_config)

    def handle_signal(*_: Any) -> None:
        logging.info("Shutdown signal received")
        server.should_exit = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    server.run()


if __name__ == "__main__":
    main()
