#!/usr/bin/env python3
"""Translate raw device metrics into canonical LED state."""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity


DEFAULT_CONFIG_PATH = "jetson/state_engine_service/config.yaml"
DEFAULT_LED_CONFIG_FILENAME = "led_config.json"
DEFAULT_RAW_STATE_FILENAME = "raw_state.json"
DEFAULT_CANONICAL_FILENAME = "canonical_state.json"
DEFAULT_HISTORY_FILENAME = "history.json"


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
            except Exception:
                logging.exception("State engine cycle failed")
                self._health.mark_error(self._identity, "state engine cycle failed")
            if run_once:
                break
            elapsed = time.monotonic() - started
            sleep_for = max(0.0, self._config.poll_interval_seconds - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

    def process_once(self) -> None:
        led_config = self._load_json(self._config.led_config_path)
        raw_state = self._load_json(self._config.raw_state_path)
        if not led_config or not raw_state:
            logging.warning("Missing led_config or raw_state; skipping cycle")
            return
        now = time.time()
        raw_timestamp = raw_state.get("timestamp")
        if raw_timestamp and now - raw_timestamp > self._config.health_rules.offline_grace_seconds:
            logging.debug(
                "Raw state timestamp is stale by %.1fs", now - raw_timestamp
            )
        canonical_leds = []
        for led in led_config.get("leds", []):
            index = led.get("index", 0)
            name = led.get("name") or f"LED {index}"
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
                "health": health,
                "activity_level": round(activity_level, 3),
                "activity_type": activity_type,
            })
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": int(now),
            "leds": canonical_leds,
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
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, sort_keys=False)
        tmp = canonical_path.with_suffix(".tmp")
        tmp.write_text(serialized, encoding="utf-8")
        tmp.replace(canonical_path)
        logging.info("Wrote %s with %d LEDs", canonical_path, len(payload.get("leds", [])))

    def _record_history(self, entry: Dict[str, Any]) -> None:
        if not self._config.history_enabled:
            return
        path = self._config.history_path
        path.parent.mkdir(parents=True, exist_ok=True)
        entries: List[Dict[str, Any]]
        entries = []
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    entries = list(existing.get("entries") or [])
                elif isinstance(existing, list):
                    entries = existing
            except json.JSONDecodeError as exc:
                logging.error("Invalid JSON in %s while recording history: %s", path, exc)
                entries = []
        entries.append(entry)
        if self._config.history_retention_seconds:
            cutoff = entry["timestamp"] - self._config.history_retention_seconds
            entries = [item for item in entries if item.get("timestamp", 0) >= cutoff]
        if self._config.history_max_entries:
            entries = entries[-self._config.history_max_entries:]
        payload = {"entries": entries}
        serialized = json.dumps(payload, indent=2, sort_keys=False)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(serialized, encoding="utf-8")
        tmp.replace(path)


def load_service_config(path: Path) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    health_rules = HealthRules(**(data.get("health_rules") or {}))
    activity_rules = ActivityRules(**(data.get("activity_rules") or {}))
    history_retention = data.get("history_retention_seconds", 86400)
    config = ServiceConfig(
        data_dir=Path(data.get("data_dir", "./data")).expanduser().resolve(),
        led_config_filename=data.get("led_config_filename", DEFAULT_LED_CONFIG_FILENAME),
        raw_state_filename=data.get("raw_state_filename", DEFAULT_RAW_STATE_FILENAME),
        canonical_state_filename=data.get("canonical_state_filename", DEFAULT_CANONICAL_FILENAME),
        poll_interval_seconds=float(data.get("poll_interval_seconds", 2)),
        health_rules=health_rules,
        activity_rules=activity_rules,
        history_enabled=bool(data.get("history_enabled", True)),
        history_filename=data.get("history_filename", DEFAULT_HISTORY_FILENAME),
        history_max_entries=int(data.get("history_max_entries", 1800)),
        history_retention_seconds=int(history_retention) if history_retention is not None else None,
        log_level=(data.get("logging", {}) or {}).get("level", "INFO"),
    )
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute canonical LED state")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process a single cycle and exit",
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
    logging.info("Starting state_engine_service writing to %s", service_config.canonical_path)
    service = StateEngineService(service_config)
    signal.signal(signal.SIGTERM, service.request_stop)
    signal.signal(signal.SIGINT, service.request_stop)
    service.run(run_once=args.once)


if __name__ == "__main__":
    main()
