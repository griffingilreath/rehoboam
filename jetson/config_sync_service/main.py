#!/usr/bin/env python3
"""Synchronize LED configuration from Home Assistant into led_config.json."""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import requests
import yaml

from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity


DEFAULT_CONFIG_PATH = "jetson/config_sync_service/config.yaml"
DEFAULT_OUTPUT_FILE = "led_config.json"


@dataclass
class HomeAssistantConfig:
    base_url: str
    token: str
    timeout_seconds: float = 10.0
    verify_ssl: bool = True

    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")


@dataclass
class TemplateConfig:
    name: str
    ip: Optional[str] = None
    type: Optional[str] = None
    ha_availability_entity: Optional[str] = None
    extra_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class ServiceConfig:
    data_dir: Path
    poll_interval_seconds: float
    led_count: int
    home_assistant: HomeAssistantConfig
    templates: TemplateConfig
    defaults: Dict[str, Optional[str]] = field(default_factory=dict)
    log_level: str = "INFO"


class HomeAssistantClient:
    def __init__(self, config: HomeAssistantConfig):
        self._config = config
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
        })
        self._session.verify = config.verify_ssl
        self._base_url = config.normalized_base_url()

    def read_entity_state(self, entity_id: str) -> Optional[str]:
        url = f"{self._base_url}/api/states/{entity_id}"
        try:
            response = self._session.get(url, timeout=self._config.timeout_seconds)
        except requests.RequestException as exc:  # pragma: no cover - network failure path
            logging.warning("Failed to reach Home Assistant entity %s: %s", entity_id, exc)
            return None

        if response.status_code == 404:
            logging.debug("Home Assistant entity %s not found", entity_id)
            return None

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - HTTP error path
            logging.error("Home Assistant error for %s: %s", entity_id, exc)
            return None

        payload = response.json()
        value = payload.get("state")
        if isinstance(value, str):
            value = value.strip()
        return value or None


class ConfigSyncService:
    def __init__(self, config: ServiceConfig):
        self.config = config
        self._client = HomeAssistantClient(config.home_assistant)
        self._data_dir = config.data_dir
        self._output_file = self._data_dir / DEFAULT_OUTPUT_FILE
        self._stop_requested = False
        self._last_serialized_payload: Optional[str] = None
        self._templates_map = self._build_templates_map(config.templates)
        self._load_last_payload_from_disk()
        self._health = ServiceHealthTracker(self._data_dir)
        self._identity = ServiceIdentity(name="config_sync_service")

    def _build_templates_map(self, templates: TemplateConfig) -> Dict[str, str]:
        mapping: Dict[str, str] = {"name": templates.name}
        if templates.ip:
            mapping["ip"] = templates.ip
        if templates.type:
            mapping["type"] = templates.type
        if templates.ha_availability_entity:
            mapping["ha_availability_entity"] = templates.ha_availability_entity
        if templates.extra_fields:
            mapping.update(templates.extra_fields)
        return mapping

    def _load_last_payload_from_disk(self) -> None:
        if not self._output_file.exists():
            return
        try:
            existing = self._output_file.read_text(encoding="utf-8")
        except OSError:
            return
        self._last_serialized_payload = existing

    def request_stop(self, *_: object) -> None:
        logging.info("Stop requested; shutting down after current sync")
        self._stop_requested = True

    def run(self, run_once: bool = False) -> None:
        self._health.mark_running(self._identity)
        while not self._stop_requested:
            started = time.monotonic()
            try:
                self.sync_once()
            except Exception:  # pragma: no cover - defensive logging
                logging.exception("Unexpected error during sync cycle")
                self._health.mark_error(self._identity, "sync cycle failed")

            if run_once:
                break

            elapsed = time.monotonic() - started
            sleep_for = max(0.0, self.config.poll_interval_seconds - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

    def sync_once(self) -> None:
        leds = [self._build_led_entry(idx) for idx in range(self.config.led_count)]
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "leds": leds,
        }
        serialized = json.dumps(payload, indent=2, sort_keys=False)
        if serialized == self._last_serialized_payload:
            logging.debug("No changes detected; led_config.json not updated")
            self._health.mark_running(self._identity)
            return

        self._data_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = self._output_file.with_suffix(".tmp")
        tmp_file.write_text(serialized, encoding="utf-8")
        tmp_file.replace(self._output_file)
        self._last_serialized_payload = serialized
        logging.info("Wrote %s with %d LED entries", self._output_file, len(leds))
        self._health.mark_running(self._identity)

    def _build_led_entry(self, index: int) -> Dict[str, object]:
        values = self._fetch_field_values(index)
        defaults = self.config.defaults
        name = values.pop("name", None) or defaults.get("name") or f"LED {index}"
        led_type = values.pop("type", None) or defaults.get("type", "unknown")

        entry: Dict[str, object] = {
            "index": index,
            "name": name,
            "type": led_type,
        }

        ip_value = values.pop("ip", None) or defaults.get("ip")
        if ip_value:
            entry["ip"] = ip_value

        availability = values.pop("ha_availability_entity", None) or defaults.get("ha_availability_entity")
        if availability:
            entry["ha_availability_entity"] = availability

        for key, value in values.items():
            fallback = defaults.get(key)
            chosen = value if value not in (None, "") else fallback
            if chosen not in (None, ""):
                entry[key] = chosen

        return entry

    def _fetch_field_values(self, index: int) -> Dict[str, Optional[str]]:
        results: Dict[str, Optional[str]] = {}
        for field_name, template in self._templates_map.items():
            if not template:
                continue
            entity_id = template.format(index=index)
            value = self._client.read_entity_state(entity_id)
            if value is None:
                logging.debug("No value for %s (entity %s)", field_name, entity_id)
            results[field_name] = value
        return results


def load_service_config(path: Path) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    try:
        ha_cfg = data["home_assistant"]
    except KeyError as exc:
        raise ValueError("home_assistant section is required") from exc

    templates_cfg = data.get("templates", {})
    extra_fields = templates_cfg.get("extra_fields", {}) or {}

    template = TemplateConfig(
        name=_require_template_field(templates_cfg, "name"),
        ip=templates_cfg.get("ip"),
        type=templates_cfg.get("type"),
        ha_availability_entity=templates_cfg.get("ha_availability_entity"),
        extra_fields=extra_fields,
    )

    config = ServiceConfig(
        data_dir=Path(data.get("data_dir", "./data")).expanduser().resolve(),
        poll_interval_seconds=float(data.get("poll_interval_seconds", 30)),
        led_count=int(data.get("led_count", 16)),
        home_assistant=HomeAssistantConfig(
            base_url=ha_cfg["base_url"],
            token=ha_cfg["token"],
            timeout_seconds=float(ha_cfg.get("timeout_seconds", 10)),
            verify_ssl=bool(ha_cfg.get("verify_ssl", True)),
        ),
        templates=template,
        defaults=data.get("defaults", {}),
        log_level=(data.get("logging", {}) or {}).get("level", "INFO"),
    )

    return config


def _require_template_field(config: Dict[str, str], key: str) -> str:
    value = config.get(key)
    if not value:
        raise ValueError(f"Template for '{key}' is required in templates section")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronize LED metadata from Home Assistant")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single sync cycle and exit",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Override log level from config",
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

    logging.info("Starting config_sync_service with %d LEDs", service_config.led_count)

    service = ConfigSyncService(service_config)

    signal.signal(signal.SIGTERM, service.request_stop)
    signal.signal(signal.SIGINT, service.request_stop)

    service.run(run_once=args.once)


if __name__ == "__main__":
    main()
