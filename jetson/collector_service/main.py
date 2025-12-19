#!/usr/bin/env python3
"""Collect raw telemetry for each LED-defined device."""
from __future__ import annotations

import argparse
import json
import logging
import platform
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests
import websocket
import yaml
from pydantic import BaseModel, Field

from jetson.common.json_store import atomic_write_json, load_json
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service
from jetson.common.config import expand_env_placeholders
from jetson.common.http import create_retry_session
from jetson.common.utils import wait_for_next_cycle

DEFAULT_CONFIG_PATH = "jetson/collector_service/config.yaml"
DEFAULT_LED_CONFIG_FILENAME = "led_config.json"
DEFAULT_RAW_STATE_FILENAME = "raw_state.json"
DEFAULT_EVENTS_LOG_FILENAME = "events.json"
RAW_STATE_SCHEMA_VERSION = "1.0"
EVENTS_SCHEMA_VERSION = "1.0"


class EventLogWriter:
    """Persist recent detailed events for dashboards/e-paper scenes."""

    def __init__(self, path: Path, max_entries: int = 200) -> None:
        self._path = path
        self._max_entries = max_entries
        self._lock = threading.Lock()

    def append_many(self, events: List[Dict[str, Any]]) -> None:
        if not events:
            return
        with self._lock:
            existing_payload = load_json(self._path, {"events": [], "schema_version": EVENTS_SCHEMA_VERSION})
            existing = existing_payload.get("events", []) if isinstance(existing_payload, dict) else []
            merged = (existing + events)[-self._max_entries :]
            payload = {"schema_version": EVENTS_SCHEMA_VERSION, "events": merged}
            atomic_write_json(self._path, payload)


class HomeAssistantConfig(BaseModel):
    base_url: str
    token: str
    timeout_seconds: float = 10.0
    verify_ssl: bool = True
    availability_states: Optional[Dict[str, bool]] = None


class PiHoleConfig(BaseModel):
    enabled: bool = False
    base_url: Optional[str] = None
    api_path: str = "/admin/api.php"
    token: Optional[str] = None
    timeout_seconds: float = 5.0


class PingConfig(BaseModel):
    count: int = 1
    timeout_seconds: float = 1.0


class EventConfig(BaseModel):
    enabled: bool = True
    reconnect_delay_seconds: float = 5.0


class ServiceConfig(BaseModel):
    data_dir: Path
    led_config_filename: str = DEFAULT_LED_CONFIG_FILENAME
    raw_state_filename: str = DEFAULT_RAW_STATE_FILENAME
    events_log_filename: str = DEFAULT_EVENTS_LOG_FILENAME
    poll_interval_seconds: float
    event_buffer_seconds: float = 10.0
    context_entities: List[str] = Field(default_factory=list)
    home_assistant: HomeAssistantConfig
    pihole: PiHoleConfig
    ping: PingConfig
    events: EventConfig
    log_level: str = "INFO"

    @property
    def led_config_path(self) -> Path:
        return self.data_dir / self.led_config_filename

    @property
    def raw_state_path(self) -> Path:
        return self.data_dir / self.raw_state_filename

    @property
    def events_log_path(self) -> Path:
        return self.data_dir / self.events_log_filename


class EventBuffer:
    """Thread-safe buffer that stores recent events for activity tracking."""

    def __init__(self, max_age_seconds: float) -> None:
        self._max_age = max_age_seconds
        self._events: Deque[Dict[str, Any]] = deque()
        self._lock = threading.Lock()

    def add(self, event: Dict[str, Any]) -> None:
        with self._lock:
            self._events.append(event)
            self._prune_locked()

    def snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._prune_locked()
            return list(self._events)

    def count_for_entities(self, entities: Iterable[str] | None) -> int:
        if not entities:
            return 0
        entity_set = {entity.lower() for entity in entities}
        now = time.time()
        threshold = now - self._max_age
        with self._lock:
            self._prune_locked(now)
            return sum(1 for event in self._events if event.get("entity_id", "").lower() in entity_set and event["timestamp"] >= threshold)

    def _prune_locked(self, now: Optional[float] = None) -> None:
        now = now or time.time()
        threshold = now - self._max_age
        while self._events and self._events[0]["timestamp"] < threshold:
            self._events.popleft()


def summarize_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    event = payload.get("event", {})
    event_type = event.get("event_type") or ""
    data = event.get("data") or {}
    if event_type == "state_changed":
        entity_id = data.get("entity_id")
        if not entity_id:
            return {}
        domain = entity_id.split(".")[0]
        new_state = data.get("new_state") or {}
        old_state = data.get("old_state") or {}
        attributes = new_state.get("attributes") or {}
        friendly = attributes.get("friendly_name") or entity_id
        state = new_state.get("state")
        context = new_state.get("context") or event.get("context") or {}
        actor = context.get("user_id") or context.get("parent_id") or context.get("source")
        summary = _derive_summary(domain, new_state, attributes, old_state)
        timestamp = event.get("time_fired") or new_state.get("last_changed")
        context = new_state.get("context") or event.get("context") or {}
        return {
            "timestamp": timestamp,
            "event_type": event_type,
            "entity_id": entity_id,
            "friendly_name": friendly,
            "domain": domain,
            "state": state,
            "summary": summary,
            "actor": actor,
            "origin": payload.get("origin"),
            "context_user_id": context.get("user_id"),
            "context_parent_id": context.get("parent_id"),
        }

    if event_type == "mobile_app_notification_action":
        # Fired when a user taps an actionable notification button on their device.
        action = data.get("action")
        tag = data.get("tag")
        timestamp = event.get("time_fired")
        context = event.get("context") or {}
        actor = context.get("user_id") or context.get("parent_id") or context.get("source")
        return {
            "timestamp": timestamp,
            "event_type": event_type,
            "domain": "notification",
            "summary": f"Notification action → {action}",
            "action": action,
            "tag": tag,
            "device_id": data.get("device_id"),
            "actor": actor,
            "origin": payload.get("origin"),
            "context_user_id": context.get("user_id"),
            "context_parent_id": context.get("parent_id"),
        }

    return {}


def _derive_summary(
    domain: str,
    new_state: Dict[str, Any],
    attributes: Dict[str, Any],
    old_state: Dict[str, Any],
) -> str:
    state = new_state.get("state")
    if domain == "light":
        brightness = attributes.get("brightness")
        if brightness is not None:
            pct = round((brightness / 255) * 100)
            return f"Brightness → {pct}%"
        return f"State → {state}"
    if domain == "cover":
        position = attributes.get("current_position")
        if position is not None:
            return f"Position → {position}%"
    if domain == "switch":
        return f"Switched {state}"
    if domain == "climate":
        temp = attributes.get("temperature")
        if temp is not None:
            return f"Setpoint → {temp}°"
    if domain == "sensor":
        return f"Reading → {attributes.get('state_class', state)}"
    old = old_state.get("state")
    if old is not None and state != old:
        return f"{old} → {state}"
    return f"State → {state}"


class HomeAssistantRestClient:
    def __init__(self, config: HomeAssistantConfig) -> None:
        self._config = config
        self._session = create_retry_session(timeout=config.timeout_seconds)
        self._session.headers.update({
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
        })
        self._session.verify = config.verify_ssl
        self._base_url = config.base_url.rstrip("/")
        self._availability_states = config.availability_states or {"on": True, "off": False}

    def read_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self._base_url}/api/states/{entity_id}"
        try:
            response = self._session.get(url, timeout=self._config.timeout_seconds)
        except requests.RequestException as exc:  # pragma: no cover - network failure path
            logging.warning("HA request failed for %s: %s", entity_id, exc)
            return None
        if response.status_code == 404:
            logging.debug("HA entity %s not found", entity_id)
            return None
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover
            logging.error("HA error for %s: %s", entity_id, exc)
            return None
        return response.json()

    def is_available(self, entity_id: str) -> Optional[bool]:
        state = self.read_state(entity_id)
        if not state:
            return None
        value = state.get("state")
        if isinstance(value, str):
            normalized = value.lower()
            if normalized in self._availability_states:
                return bool(self._availability_states[normalized])
        return None


class PiHoleClient:
    def __init__(self, config: PiHoleConfig) -> None:
        self._enabled = config.enabled and bool(config.base_url)
        self._base_url = config.base_url.rstrip("/") if config.base_url else ""
        self._api_path = config.api_path or "/admin/api.php"
        self._token = config.token
        self._timeout = config.timeout_seconds
        self._session = create_retry_session(timeout=config.timeout_seconds)

    def summary(self) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return None
        attempts: list[tuple[str, Dict[str, Any]]] = []
        attempts.append((f"{self._base_url}{self._api_path}", {"summaryRaw": 1}))
        attempts.append((f"{self._base_url}/api/summary", {}))
        attempts.append((f"{self._base_url}/api", {"summary": 1}))

        for url, params in attempts:
            params = dict(params)
            if self._token:
                params.setdefault("auth", self._token)
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    return data
            except requests.RequestException:
                continue
        logging.warning("Pi-hole request failed for all known endpoints")
        return None


class Pinger:
    def __init__(self, config: PingConfig) -> None:
        self._count = max(1, config.count)
        self._timeout = max(0.1, config.timeout_seconds)
        self._platform = platform.system().lower()

    def ping(self, host: str) -> Tuple[bool, Optional[float]]:
        if not host:
            return False, None
        if self._platform == "windows":
            cmd = ["ping", "-n", str(self._count), "-w", str(int(self._timeout * 1000)), host]
        else:
            cmd = ["ping", "-c", str(self._count), "-W", str(int(self._timeout)), host]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except OSError as exc:  # pragma: no cover - ping not available
            logging.error("Ping command failed: %s", exc)
            return False, None
        reachable = completed.returncode == 0
        rtt = self._parse_rtt_ms(completed.stdout) if reachable else None
        return reachable, rtt

    @staticmethod
    def _parse_rtt_ms(output: str) -> Optional[float]:
        for line in output.splitlines():
            if "round-trip" in line or "rtt" in line or "Average =" in line:
                numbers = [token for token in line.replace("=", "/").replace("ms", "").split("/") if token.strip()]
                try:
                    values = [float(value) for value in numbers]
                except ValueError:
                    continue
                if values:
                    return values[min(1, len(values) - 1)]
        return None


class HomeAssistantEventStream(threading.Thread):
    """Background thread that listens to HA websocket events."""

    def __init__(self, config: HomeAssistantConfig, handler: Callable[[Dict[str, Any]], None], event_config: EventConfig) -> None:
        super().__init__(daemon=True)
        self._config = config
        self._handler = handler
        self._event_config = event_config
        self._stop = threading.Event()

    def run(self) -> None:
        delay = self._event_config.reconnect_delay_seconds
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self._listen_once()
            except Exception as exc:
                logging.warning("Event stream disconnected: %s", exc)
            
            # Reset backoff if we stayed connected for a while
            if time.monotonic() - started > 30.0:
                delay = self._event_config.reconnect_delay_seconds

            if not self._stop.is_set():
                logging.info("Reconnecting to Home Assistant event stream in %.1fs...", delay)
                if self._stop.wait(delay):
                    break
                delay = min(delay * 2, 300.0)

    def stop(self) -> None:
        self._stop.set()

    def _listen_once(self) -> None:
        ws_url = self._websocket_url(self._config.base_url)
        logging.info("Connecting to Home Assistant websocket %s", ws_url)
        ws = websocket.create_connection(ws_url, timeout=self._config.timeout_seconds, sslopt={"cert_reqs": 2 if self._config.verify_ssl else 0})
        try:
            self._authenticate(ws)
            self._subscribe(ws)
            while not self._stop.is_set():
                message = ws.recv()
                if not message:
                    continue
                payload = json.loads(message)
                if payload.get("type") != "event":
                    continue
                summary = summarize_event(payload)
                if summary:
                    summary.setdefault("timestamp_epoch", time.time())
                    self._handler(summary)
        finally:
            ws.close()

    def _authenticate(self, ws: websocket.WebSocket) -> None:
        message = ws.recv()
        payload = json.loads(message)
        if payload.get("type") != "auth_required":
            raise RuntimeError("Unexpected websocket handshake response")
        ws.send(json.dumps({"type": "auth", "access_token": self._config.token}))
        response = json.loads(ws.recv())
        if response.get("type") != "auth_ok":
            raise RuntimeError(f"Authentication failed: {response}")

    def _subscribe(self, ws: websocket.WebSocket) -> None:
        # State changes for activity tracking, plus actionable notification responses for feedback loops.
        ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
        ws.send(json.dumps({"id": 2, "type": "subscribe_events", "event_type": "mobile_app_notification_action"}))

    @staticmethod
    def _websocket_url(base_url: str) -> str:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Home Assistant base_url must be http or https")
        scheme = "ws" if parsed.scheme == "http" else "wss"
        netloc = parsed.netloc
        return f"{scheme}://{netloc}/api/websocket"


class CollectorService:
    def __init__(self, config: ServiceConfig):
        self._config = config
        self._ha = HomeAssistantRestClient(config.home_assistant)
        self._pinger = Pinger(config.ping)
        self._pihole = PiHoleClient(config.pihole)
        self._event_buffer = EventBuffer(config.event_buffer_seconds)
        self._event_archive: Deque[Dict[str, Any]] = deque(maxlen=2000)
        self._archive_lock = threading.Lock()
        self._event_log_writer = EventLogWriter(config.events_log_path)
        self._context_entities = config.context_entities
        self._event_stream = self._start_event_stream()
        self._stop_requested = False
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="collector_service")

    def _start_event_stream(self) -> Optional[HomeAssistantEventStream]:
        if not self._config.events.enabled:
            logging.info("Event stream disabled")
            return None
        stream = HomeAssistantEventStream(
            self._config.home_assistant,
            handler=self._handle_event,
            event_config=self._config.events,
        )
        stream.start()
        return stream

    def _handle_event(self, event: Dict[str, Any]) -> None:
        self._event_buffer.add(event)
        with self._archive_lock:
            self._event_archive.append(event)

    def request_stop(self, *_: Any) -> None:
        logging.info("Stop requested; finishing current cycle")
        self._stop_requested = True
        if self._event_stream:
            self._event_stream.stop()

    def run(self, run_once: bool = False) -> None:
        self._health.mark_running(self._identity)
        while not self._stop_requested:
            started = time.monotonic()
            try:
                self.collect_once()
            except Exception as exc:
                logging.exception("Collector cycle failed")
                self._health.mark_error(self._identity, f"collector cycle failed: {exc}")
            if run_once:
                break
            wait_for_next_cycle(started, self._config.poll_interval_seconds)

    def collect_once(self) -> None:
        led_config = self._load_led_config()
        if not led_config:
            logging.warning("No led_config.json available yet; skipping cycle")
            return
        devices: Dict[str, Dict[str, Any]] = {}
        for led in led_config.get("leds", []):
            name = led.get("name") or f"LED {led.get('index', '?')}"
            devices[name] = self._collect_device_state(led)
        context_snapshot = self._build_context_snapshot()
        payload = {
            "schema_version": RAW_STATE_SCHEMA_VERSION,
            "timestamp": int(time.time()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "devices": devices,
            "events": self._event_buffer.snapshot(),
            "context": context_snapshot,
        }
        raw_state_path = self._config.raw_state_path
        atomic_write_json(raw_state_path, payload)
        logging.info("Wrote %s for %d devices", raw_state_path, len(devices))
        self._health.mark_running(self._identity)
        self._flush_event_log()

    def _load_led_config(self) -> Optional[Dict[str, Any]]:
        path = self._config.led_config_path
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging.error("Invalid JSON in %s: %s", path, exc)
            return None

    def _collect_device_state(self, led_entry: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        ip = led_entry.get("ip")
        if ip:
            # Run pings in parallel if we have many devices to avoid blocking
            # For now, simple optimization: reduce timeout/count if many failures detected
            # Future: use asyncio or ThreadPoolExecutor for pings
            reachable, rtt_ms = self._pinger.ping(ip)
            result["reachable"] = reachable
            if rtt_ms is not None:
                result["rtt_ms"] = rtt_ms
        availability_entity = led_entry.get("ha_availability_entity")
        if availability_entity:
            availability = self._ha.is_available(availability_entity)
            if availability is not None:
                result["ha_available"] = availability
        event_entities = self._extract_event_entities(led_entry)
        if event_entities:
            result["events_last_window"] = self._event_buffer.count_for_entities(event_entities)
        if (led_entry.get("type") or "").lower() == "pihole":
            summary = self._pihole.summary()
            if summary:
                result["qps"] = summary.get("queries_last_minute", 0) / 60.0
                blocked = summary.get("ads_blocked_today", 0)
                total = summary.get("dns_queries_today", 0) or 1
                result["blocked_ratio"] = blocked / total
                result["pihole_status"] = summary.get("status")
        return result

    @staticmethod
    def _extract_event_entities(led_entry: Dict[str, Any]) -> List[str]:
        entities = led_entry.get("event_entities")
        if not entities:
            return []
        if isinstance(entities, str):
            return [entity.strip() for entity in entities.split(",") if entity.strip()]
        if isinstance(entities, list):
            return [str(entity).strip() for entity in entities if str(entity).strip()]
        return []

    def _flush_event_log(self) -> None:
        with self._archive_lock:
            if not self._event_archive:
                return
            batch = list(self._event_archive)
            self._event_archive.clear()
        self._event_log_writer.append_many(batch)

    def _build_context_snapshot(self) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {
            "timestamp": int(time.time()),
            "daypart": self._derive_daypart(),
            "entities": {},
        }
        flags = {"occupied": False, "rain_expected": False}
        for entity_id in self._context_entities:
            state_obj = self._ha.read_state(entity_id)
            if not state_obj:
                continue
            snapshot["entities"][entity_id] = {
                "state": state_obj.get("state"),
                "attributes": state_obj.get("attributes", {}),
            }
            self._update_flags_from_entity(flags, entity_id, state_obj)
        snapshot["flags"] = flags
        return snapshot

    @staticmethod
    def _derive_daypart() -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 22:
            return "evening"
        return "night"

    @staticmethod
    def _update_flags_from_entity(flags: Dict[str, bool], entity_id: str, state_obj: Dict[str, Any]) -> None:
        domain = entity_id.split(".")[0]
        state = (state_obj.get("state") or "").lower()
        attributes = state_obj.get("attributes") or {}
        if domain in {"person", "device_tracker"}:
            if state not in {"not_home", "away", ""}:
                flags["occupied"] = True
        if domain == "binary_sensor" and "rain" in entity_id:
            flags["rain_expected"] = state in {"on", "rain", "wet"}
        if domain == "weather":
            condition = attributes.get("condition", "").lower()
            if "rain" in condition or "precip" in condition:
                flags["rain_expected"] = True


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data = expand_env_placeholders(data)
    overrides = overrides or RunnerOverrides()
    
    if overrides.data_dir:
        data["data_dir"] = overrides.data_dir
    else:
        if "data_dir" not in data:
            data["data_dir"] = "./data"
    
    # Ensure paths are expanded/resolved even if coming from YAML
    if "data_dir" in data:
        data["data_dir"] = Path(data["data_dir"]).expanduser().resolve()
    
    if overrides.poll_interval_seconds:
        data["poll_interval_seconds"] = overrides.poll_interval_seconds
    
    if overrides.log_level:
        data["log_level"] = overrides.log_level
        
    return ServiceConfig(**data)


def main() -> None:
    def _create_service(config: ServiceConfig, _: argparse.Namespace) -> CollectorService:
        logging.info(
            "Collector will write %s every %.1fs", config.raw_state_path, config.poll_interval_seconds
        )
        return CollectorService(config)

    run_service(
        service_name="collector_service",
        description="Collect raw LED telemetry and context",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
    )


if __name__ == "__main__":
    main()
