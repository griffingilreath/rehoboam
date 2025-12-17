#!/usr/bin/env python3
"""Synchronize LED configuration from Home Assistant into led_config.json."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List

import aiohttp
import requests
import yaml

from jetson.common.json_store import atomic_write_json
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service
from jetson.common.config import expand_env_placeholders

DEFAULT_CONFIG_PATH = "jetson/config_sync_service/config.yaml"
DEFAULT_OUTPUT_FILE = "led_config.json"
LED_CONFIG_SCHEMA_VERSION = "1.0"


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

    # Async method
    async def read_entity_state_async(self, session: aiohttp.ClientSession, entity_id: str) -> Optional[str]:
        url = f"{self._base_url}/api/states/{entity_id}"
        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "Content-Type": "application/json",
        }
        ssl_context = None if self._config.verify_ssl else False
        
        try:
            async with session.get(url, headers=headers, ssl=ssl_context, timeout=self._config.timeout_seconds) as response:
                if response.status == 404:
                    logging.debug("Home Assistant entity %s not found", entity_id)
                    return None
                if response.status >= 400:
                    logging.error("Home Assistant error for %s: %s", entity_id, response.status)
                    return None
                
                payload = await response.json()
                value = payload.get("state")
                if isinstance(value, str):
                    value = value.strip()
                return value or None
        except asyncio.TimeoutError:
             logging.warning("HA request timed out for %s", entity_id)
             return None
        except Exception as exc:
            logging.warning("Failed to reach Home Assistant entity %s: %s", entity_id, exc)
            return None

    # Sync method kept for reference/fallback
    def read_entity_state(self, entity_id: str) -> Optional[str]:
        url = f"{self._base_url}/api/states/{entity_id}"
        try:
            response = self._session.get(url, timeout=self._config.timeout_seconds)
        except requests.RequestException as exc:
            logging.warning("Failed to reach Home Assistant entity %s: %s", entity_id, exc)
            return None

        if response.status_code == 404:
            logging.debug("Home Assistant entity %s not found", entity_id)
            return None

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
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
        try:
            asyncio.run(self._run_async(run_once))
        except KeyboardInterrupt:
            self.request_stop()

    async def _run_async(self, run_once: bool) -> None:
        self._health.mark_running(self._identity)
        async with aiohttp.ClientSession() as session:
            while not self._stop_requested:
                started = time.monotonic()
                try:
                    await self.sync_once_async(session)
                except Exception:
                    logging.exception("Unexpected error during sync cycle")
                    self._health.mark_error(self._identity, "sync cycle failed")

                if run_once:
                    break

                elapsed = time.monotonic() - started
                sleep_for = max(0.0, self.config.poll_interval_seconds - elapsed)
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)

    async def sync_once_async(self, session: aiohttp.ClientSession) -> None:
        # Create tasks for all LEDs in parallel
        tasks = []
        for idx in range(self.config.led_count):
            tasks.append(self._build_led_entry_async(idx, session))
            
        leds = await asyncio.gather(*tasks)
        
        payload = {
            "schema_version": LED_CONFIG_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "leds": list(leds),
        }
        serialized = json.dumps(payload, indent=2, sort_keys=False)
        if serialized == self._last_serialized_payload:
            logging.debug("No changes detected; led_config.json not updated")
            self._health.mark_running(self._identity)
            return

        atomic_write_json(self._output_file, payload)
        self._last_serialized_payload = serialized
        logging.info("Wrote %s with %d LED entries", self._output_file, len(leds))
        self._health.mark_running(self._identity)

    # Legacy sync method for tests/compatibility
    def sync_once(self) -> None:
        leds = [self._build_led_entry(idx) for idx in range(self.config.led_count)]
        payload = {
            "schema_version": LED_CONFIG_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "leds": leds,
        }
        serialized = json.dumps(payload, indent=2, sort_keys=False)
        if serialized == self._last_serialized_payload:
            logging.debug("No changes detected; led_config.json not updated")
            self._health.mark_running(self._identity)
            return

        atomic_write_json(self._output_file, payload)
        self._last_serialized_payload = serialized
        logging.info("Wrote %s with %d LED entries", self._output_file, len(leds))
        self._health.mark_running(self._identity)

    async def _build_led_entry_async(self, index: int, session: aiohttp.ClientSession) -> Dict[str, object]:
        values = await self._fetch_field_values_async(index, session)
        return self._construct_led_entry(index, values)

    def _build_led_entry(self, index: int) -> Dict[str, object]:
        values = self._fetch_field_values(index)
        return self._construct_led_entry(index, values)

    def _construct_led_entry(self, index: int, values: Dict[str, Optional[str]]) -> Dict[str, object]:
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

    async def _fetch_field_values_async(self, index: int, session: aiohttp.ClientSession) -> Dict[str, Optional[str]]:
        results: Dict[str, Optional[str]] = {}
        # We can also parallelize fetching fields for a single LED if needed, 
        # but usually fields are derived from the templates map.
        
        # In this specific case, we are iterating over templates. 
        # Since we are already parallelizing across LEDs, doing sequential fetches for fields within one LED is probably fine 
        # unless there are MANY fields per LED (usually just a few).
        # Let's keep it simple: 
        # Wait, network calls are inside the loop! 
        # "value = self._client.read_entity_state(entity_id)"
        # We should parallelize this too.
        
        field_tasks = []
        field_names = []
        
        for field_name, template in self._templates_map.items():
            if not template:
                continue
            entity_id = template.format(index=index)
            field_names.append((field_name, entity_id))
            field_tasks.append(self._client.read_entity_state_async(session, entity_id))
            
        if field_tasks:
            values = await asyncio.gather(*field_tasks)
            for (field_name, entity_id), value in zip(field_names, values):
                if value is None:
                    logging.debug("No value for %s (entity %s)", field_name, entity_id)
                results[field_name] = value
                
        return results

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


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
        data = expand_env_placeholders(data)
    overrides = overrides or RunnerOverrides()

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

    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    poll_interval = overrides.poll_interval_seconds or float(data.get("poll_interval_seconds", 30))
    log_level = overrides.log_level or (data.get("logging", {}) or {}).get("level", "INFO")

    config = ServiceConfig(
        data_dir=data_dir,
        poll_interval_seconds=poll_interval,
        led_count=int(data.get("led_count", 16)),
        home_assistant=HomeAssistantConfig(
            base_url=ha_cfg["base_url"],
            token=ha_cfg["token"],
            timeout_seconds=float(ha_cfg.get("timeout_seconds", 10)),
            verify_ssl=bool(ha_cfg.get("verify_ssl", True)),
        ),
        templates=template,
        defaults=data.get("defaults", {}),
        log_level=log_level,
    )

    return config


def _require_template_field(config: Dict[str, str], key: str) -> str:
    value = config.get(key)
    if not value:
        raise ValueError(f"Template for '{key}' is required in templates section")
    return value


def main() -> None:
    def _create_service(config: ServiceConfig, _: argparse.Namespace) -> ConfigSyncService:
        logging.info("Config sync configured for %d LEDs", config.led_count)
        return ConfigSyncService(config)

    run_service(
        service_name="config_sync_service",
        description="Synchronize LED metadata from Home Assistant helpers",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
    )


if __name__ == "__main__":
    main()
