"""Shared command-line runner for Jetson services."""
from __future__ import annotations

import argparse
import logging
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, TypeVar
import os

class ServiceProtocol(Protocol):
    """Simple protocol implemented by all long-running services."""

    def run(self, run_once: bool = False) -> None:  # pragma: no cover - structural
        ...

    def request_stop(self, *_: Any) -> None:  # pragma: no cover - structural
        ...


@dataclass
class RunnerOverrides:
    """Standard overrides that can be applied from the CLI."""

    data_dir: Optional[Path] = None
    log_level: Optional[str] = None
    poll_interval_seconds: Optional[float] = None


def _configure_logging(level_name: Optional[str]) -> None:
    level = (level_name or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


ConfigT = TypeVar("ConfigT")


def run_service(
    *,
    service_name: str,
    description: str,
    default_config_path: str,
    load_config: Callable[[Path, RunnerOverrides], ConfigT],
    create_service: Callable[[ConfigT, argparse.Namespace], ServiceProtocol],
    add_arguments: Optional[Callable[[argparse.ArgumentParser], None]] = None,
    supports_once: bool = True,
    supports_interval_override: bool = True,
) -> None:
    """Bootstrap a service with shared CLI/override handling."""

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        default=default_config_path,
        help=f"Path to YAML config file (default: {default_config_path})",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Override log level from config",
    )
    parser.add_argument(
        "--data-dir",
        help="Override data directory from config",
    )
    if supports_once:
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single iteration and exit",
        )
    if supports_interval_override:
        parser.add_argument(
            "--interval",
            type=float,
            help="Override poll interval seconds for this run",
        )
    if add_arguments:
        add_arguments(parser)
    args = parser.parse_args()

    # Load env secrets early so ${VAR} placeholders in YAML can be expanded by services.
    # Prefer /etc/rehoboam/secrets.env then a local .env if present.
    for env_file in (Path("/etc/rehoboam/secrets.env"), Path(".env")):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

    overrides = RunnerOverrides(
        data_dir=Path(args.data_dir).expanduser().resolve() if args.data_dir else None,
        log_level=args.log_level,
        poll_interval_seconds=getattr(args, "interval", None),
    )

    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path, overrides)
    log_level = overrides.log_level or getattr(config, "log_level", None)
    _configure_logging(log_level)

    logging.info("Starting %s", service_name)
    service = create_service(config, args)

    if hasattr(service, "request_stop"):
        signal.signal(signal.SIGTERM, service.request_stop)
        signal.signal(signal.SIGINT, service.request_stop)

    _dispatch_service_run(service, getattr(args, "once", False) if supports_once else False)


def _dispatch_service_run(service: ServiceProtocol, run_once: bool) -> None:
    """Best-effort invocation supporting run(run_once=bool) or run()/run_once()."""
    try:
        service.run(run_once=run_once)
        return
    except TypeError:
        if run_once and hasattr(service, "run_once"):
            service.run_once()
        else:
            service.run()

