#!/usr/bin/env python3
"""Translate raw device metrics into canonical LED state."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from jetson.common.json_store import atomic_write_json, load_json
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service
from jetson.common.utils import wait_for_next_cycle


DEFAULT_CONFIG_PATH = str(Path(__file__).parent / "config.yaml")
DEFAULT_LED_CONFIG_FILENAME = "led_config.json"
DEFAULT_RAW_STATE_FILENAME = "raw_state.json"
DEFAULT_CANONICAL_FILENAME = "canonical_state.json"
DEFAULT_HISTORY_FILENAME = "history.json"
CANONICAL_SCHEMA_VERSION = "1.0"
HISTORY_SCHEMA_VERSION = "1.0"


@dataclass
class HealthRules:
    ping_timeout_ms: float = 500.0
    warning_latency_ms: float = 150.0
    offline_grace_seconds: float = 30.0
    require_availability_entity: bool = False


@dataclass
class ActivityRules:
    decay_per_second: float = 0.2
    event_boost: float = 0.3
    pihole_qps_scale: float = 0.02
    max_activity: float = 1.0


@dataclass
class ServiceConfig:
    data_dir: Path
    led_config_filename: str
    raw_state_filename: str
    canonical_state_filename: str
    poll_interval_seconds: float
    health_rules: HealthRules
    activity_rules: ActivityRules
    history_enabled: bool = True
    history_filename: str = DEFAULT_HISTORY_FILENAME
    history_max_entries: int = 1800
    history_retention_seconds: Optional[int] = 86400
    log_level: str = "INFO"

    @property
    def led_config_path(self) -> Path:
        return self.data_dir / self.led_config_filename

    @property
    def raw_state_path(self) -> Path:
        return self.data_dir / self.raw_state_filename

    @property
    def canonical_path(self) -> Path:
        return self.data_dir / self.canonical_state_filename

    @property
    def history_path(self) -> Path:
        return self.data_dir / self.history_filename


@dataclass
class LedState:
    last_health: str = "UNKNOWN"
    activity_level: float = 0.0
    activity_type: str = "none"
    last_update: float = 0.0


class StateEngineService:
    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._per_led_state: Dict[int, LedState] = {}
        self._stop_requested = False
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="state_engine_service")

    def request_stop(self, *_: Any) -> None:
        logging.info("Stop requested; finishing current computation")
        self._stop_requested = True

    def run(self, run_once: bool = False) -> None:
        self._health.mark_running(self._identity)
        while not self._stop_requested:
            started = time.monotonic()
            try:
                self.process_once()
            except Exception as exc:
                logging.exception("State engine cycle failed")
                self._health.mark_error(self._identity, f"state engine cycle failed: {exc}")
            if run_once:
                break
            wait_for_next_cycle(started, self._config.poll_interval_seconds)

    def process_once(self) -> None:
        led_config = self._load_json(self._config.led_config_path)
        raw_state = self._load_json(self._config.raw_state_path)
        if not led_config or not raw_state:
            logging.warning("Missing led_config or raw_state; skipping cycle")
            return
        now = time.time()
        raw_timestamp = raw_state.get("timestamp")
        context = raw_state.get("context")
        if raw_timestamp and now - raw_timestamp > self._config.health_rules.offline_grace_seconds:
            logging.debug(
                "Raw state timestamp is stale by %.1fs", now - raw_timestamp
            )
        canonical_leds = []
        for led in led_config.get("leds", []):
            index = led.get("index", 0)
            name = led.get("name") or f"LED {index}"
            led_type = led.get("type") or "unknown"
            device_state = raw_state.get("devices", {}).get(name)
            led_state = self._per_led_state.setdefault(index, LedState(last_update=now))
            health = self._determine_health(led, device_state, raw_timestamp)
            activity_level, activity_type = self._update_activity(led, device_state, led_state, now)
            led_state.last_health = health
            led_state.activity_level = activity_level
            led_state.activity_type = activity_type
            led_state.last_update = now
            canonical_leds.append({
                "index": index,
                "name": name,
                "type": led_type,
                "health": health,
                "activity_level": round(activity_level, 3),
                "activity_type": activity_type,
            })
        payload = {
            "schema_version": CANONICAL_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": int(now),
            "leds": canonical_leds,
            "context": context or {},
        }
        self._write_canonical(payload)
        self._record_history(payload)
        self._health.mark_running(self._identity)

    def _determine_health(
        self,
        led_entry: Dict[str, Any],
        device_state: Optional[Dict[str, Any]],
        raw_timestamp: Optional[int],
    ) -> str:
        if not device_state:
            if raw_timestamp is None:
                return "UNKNOWN"
            if time.time() - raw_timestamp > self._config.health_rules.offline_grace_seconds:
                return "UNKNOWN"
            return "UNKNOWN"
        reachable = device_state.get("reachable")
        latency = device_state.get("rtt_ms")
        ha_available = device_state.get("ha_available")
        rules = self._config.health_rules
        if reachable is False:
            return "ERROR"
        if rules.require_availability_entity and ha_available is False:
            return "ERROR"
        if ha_available is False and reachable is not True:
            return "ERROR"
        if reachable is True and latency is not None and latency > rules.warning_latency_ms:
            return "WARNING"
        if reachable is True:
            return "OK"
        if ha_available is True:
            return "OK"
        return "UNKNOWN"

    def _update_activity(
        self,
        led_entry: Dict[str, Any],
        device_state: Optional[Dict[str, Any]],
        previous: LedState,
        now: float,
    ) -> tuple[float, str]:
        rules = self._config.activity_rules
        delta = max(0.0, now - previous.last_update) if previous.last_update else rules.decay_per_second
        decayed = max(0.0, previous.activity_level - rules.decay_per_second * delta)
        boost = 0.0
        activity_type = "none"
        if device_state:
            events = device_state.get("events_last_window", 0) or 0
            if events:
                boost += rules.event_boost * min(events, 5)
                activity_type = led_entry.get("activity_hint", "light_change")
            qps = device_state.get("qps")
            if qps:
                boost += qps * rules.pihole_qps_scale
                activity_type = led_entry.get("activity_hint", "dns_queries")
        level = min(rules.max_activity, decayed + boost)
        if level <= 0.01:
            activity_type = "none"
        elif activity_type == "none":
            activity_type = previous.activity_type
        return level, activity_type or "none"

    @staticmethod
    def _load_json(path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            logging.debug("File %s not found", path)
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging.error("Invalid JSON in %s: %s", path, exc)
            return None

    def _write_canonical(self, payload: Dict[str, Any]) -> None:
        canonical_path = self._config.canonical_path
        atomic_write_json(canonical_path, payload)
        logging.info("Wrote %s with %d LEDs", canonical_path, len(payload.get("leds", [])))

    def _record_history(self, entry: Dict[str, Any]) -> None:
        if not self._config.history_enabled:
            return
        path = self._config.history_path
        
        # Optimization: Don't read full history every time if just appending
        # For now, we read full history to enforce retention limits (rolling window)
        # Future: Use a proper time-series DB (InfluxDB/SQLite) for long-term storage
        
        existing = load_json(path, {"schema_version": HISTORY_SCHEMA_VERSION, "entries": []})
        if isinstance(existing, dict):
            entries: List[Dict[str, Any]] = list(existing.get("entries") or [])
        elif isinstance(existing, list):
            entries = list(existing)
        else:
            entries = []
        if "schema_version" not in entry:
            entry = {**entry, "schema_version": CANONICAL_SCHEMA_VERSION}
        entries.append(entry)
        if self._config.history_retention_seconds:
            cutoff = entry["timestamp"] - self._config.history_retention_seconds
            entries = [item for item in entries if item.get("timestamp", 0) >= cutoff]
        if self._config.history_max_entries:
            entries = entries[-self._config.history_max_entries:]
        payload = {"schema_version": HISTORY_SCHEMA_VERSION, "entries": entries}
        atomic_write_json(path, payload)


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = overrides or RunnerOverrides()
    health_rules = HealthRules(**(data.get("health_rules") or {}))
    activity_rules = ActivityRules(**(data.get("activity_rules") or {}))
    history_retention = data.get("history_retention_seconds", 86400)
    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    poll_interval = overrides.poll_interval_seconds or float(data.get("poll_interval_seconds", 2))
    log_level = overrides.log_level or (data.get("logging", {}) or {}).get("level", "INFO")
    config = ServiceConfig(
        data_dir=data_dir,
        led_config_filename=data.get("led_config_filename", DEFAULT_LED_CONFIG_FILENAME),
        raw_state_filename=data.get("raw_state_filename", DEFAULT_RAW_STATE_FILENAME),
        canonical_state_filename=data.get("canonical_state_filename", DEFAULT_CANONICAL_FILENAME),
        poll_interval_seconds=poll_interval,
        health_rules=health_rules,
        activity_rules=activity_rules,
        history_enabled=bool(data.get("history_enabled", True)),
        history_filename=data.get("history_filename", DEFAULT_HISTORY_FILENAME),
        history_max_entries=int(data.get("history_max_entries", 1800)),
        history_retention_seconds=int(history_retention) if history_retention is not None else None,
        log_level=log_level,
    )
    return config


def main() -> None:
    def _create_service(config: ServiceConfig, _: argparse.Namespace) -> StateEngineService:
        logging.info("State engine emitting %s", config.canonical_path)
        return StateEngineService(config)

    run_service(
        service_name="state_engine_service",
        description="Translate raw telemetry into canonical LED state",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
    )


if __name__ == "__main__":
    main()
