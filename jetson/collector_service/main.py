#!/usr/bin/env python3
"""Collect raw telemetry for each LED-defined device."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import platform
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
import requests
import websocket
import yaml

from jetson.common.json_store import atomic_write_json, load_json
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service
from jetson.common.config import expand_env_placeholders
from jetson.common.home_assistant import HomeAssistantClient, HomeAssistantConfig

DEFAULT_CONFIG_PATH = "jetson/collector_service/config.yaml"
DEFAULT_LED_CONFIG_FILENAME = "led_config.json"
DEFAULT_RAW_STATE_FILENAME = "raw_state.json"
DEFAULT_EVENTS_LOG_FILENAME = "events.json"
RAW_STATE_SCHEMA_VERSION = "1.0"


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
            existing_payload = load_json(self._path, {"events": []})
            existing = existing_payload.get("events", []) if isinstance(existing_payload, dict) else []
            merged = (existing + events)[-self._max_entries :]
            payload = {"events": merged}
            atomic_write_json(self._path, payload)


@dataclass
class PiHoleConfig:
    enabled: bool = False
    base_url: str | None = None
    api_path: str = "/admin/api.php"
    token: str | None = None
    timeout_seconds: float = 5.0


@dataclass
class PingConfig:
    count: int = 1
    timeout_seconds: float = 1.0


@dataclass
class EventConfig:
    enabled: bool = True
    reconnect_delay_seconds: float = 5.0


@dataclass
class ServiceConfig:
    data_dir: Path
    led_config_filename: str
    raw_state_filename: str
    events_log_filename: str
    poll_interval_seconds: float
    event_buffer_seconds: float
    context_entities: List[str]
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
    data = event.get("data") or {}
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


class PiHoleClient:
    def __init__(self, config: PiHoleConfig) -> None:
        self._enabled = config.enabled and bool(config.base_url)
        self._base_url = config.base_url.rstrip("/") if config.base_url else ""
        self._api_path = config.api_path or "/admin/api.php"
        self._token = config.token
        self._timeout = config.timeout_seconds
        self._session = requests.Session()

    def summary(self) -> Optional[Dict[str, Any]]:
        # Synchronous implementation kept for reference
        if not self._enabled:
            return None
        attempts = self._get_attempts()
        for url, params in attempts:
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

    async def summary_async(self, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return None
        attempts = self._get_attempts()
        
        for url, params in attempts:
            try:
                # Construct query string manually or let aiohttp handle it
                async with session.get(url, params=params, timeout=self._timeout) as response:
                    if response.status == 404:
                        continue
                    if response.status >= 400:
                        continue
                    data = await response.json()
                    if isinstance(data, dict):
                        return data
            except Exception:
                continue
        logging.warning("Pi-hole request failed for all known endpoints (checked v5 and v6 paths)")
        return None

    def _get_attempts(self) -> List[Tuple[str, Dict[str, Any]]]:
        attempts: list[tuple[str, Dict[str, Any]]] = []
        # v5: /admin/api.php?summaryRaw=1&auth=<token>
        attempts.append((f"{self._base_url}{self._api_path}", {"summaryRaw": "1"}))
        # v6: common candidates observed in docs/community
        attempts.append((f"{self._base_url}/api/summary", {}))
        attempts.append((f"{self._base_url}/api", {"summary": "1"}))
        
        final_attempts = []
        for url, params in attempts:
            p = dict(params)
            if self._token:
                p.setdefault("auth", self._token)
            final_attempts.append((url, p))
        return final_attempts


class Pinger:
    def __init__(self, config: PingConfig) -> None:
        self._count = max(1, config.count)
        self._timeout = max(0.1, config.timeout_seconds)
        self._platform = platform.system().lower()

    def ping(self, host: str) -> Tuple[bool, Optional[float]]:
        # Synchronous implementation
        if not host:
            return False, None
        cmd = self._get_cmd(host)
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except OSError as exc:
            logging.error("Ping command failed: %s", exc)
            return False, None
        reachable = completed.returncode == 0
        rtt = self._parse_rtt_ms(completed.stdout) if reachable else None
        return reachable, rtt

    async def ping_async(self, host: str) -> Tuple[bool, Optional[float]]:
        if not host:
            return False, None
        cmd = self._get_cmd(host)
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            stdout_decoded = stdout.decode("utf-8", errors="ignore")
            
            reachable = process.returncode == 0
            rtt = self._parse_rtt_ms(stdout_decoded) if reachable else None
            return reachable, rtt
        except OSError as exc:
             logging.error("Ping command failed: %s", exc)
             return False, None

    def _get_cmd(self, host: str) -> List[str]:
        if self._platform == "windows":
            return ["ping", "-n", str(self._count), "-w", str(int(self._timeout * 1000)), host]
        else:
            return ["ping", "-c", str(self._count), "-W", str(int(self._timeout)), host]

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
        self._client = HomeAssistantClient(config)
        self._client = HomeAssistantClient(config)

    def run(self) -> None:  # pragma: no cover - network loop
        while not self._stop.is_set():
            try:
                self._listen_once()
            except Exception as exc:
                logging.warning("Event stream disconnected: %s", exc)
            if not self._stop.wait(self._event_config.reconnect_delay_seconds):
                logging.info("Reconnecting to Home Assistant event stream...")

    def stop(self) -> None:
        self._stop.set()

    def _listen_once(self) -> None:
        ws_url = self._client.websocket_url()
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
                event = payload.get("event", {})
                data = event.get("data", {})
                entity_id = data.get("entity_id")
                if not entity_id:
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
        ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))


class CollectorService:
    def __init__(self, config: ServiceConfig):
        self._config = config
        self._ha = HomeAssistantClient(config.home_assistant)
        self._pinger = Pinger(config.ping)
        self._pihole = PiHoleClient(config.pihole)
        self._event_buffer = EventBuffer(config.event_buffer_seconds)
        self._event_archive: Deque[Dict[str, Any]] = deque()
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
        # Bootstraps the async event loop for the collector
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
                    await self.collect_once_async(session)
                except Exception:
                    logging.exception("Collector cycle failed")
                    self._health.mark_error(self._identity, "collector cycle failed")
                if run_once:
                    break
                elapsed = time.monotonic() - started
                sleep_for = max(0.0, self._config.poll_interval_seconds - elapsed)
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)

    async def collect_once_async(self, session: aiohttp.ClientSession) -> None:
        led_config = self._load_led_config()
        if not led_config:
            logging.warning("No led_config.json available yet; skipping cycle")
            return

        # Parallelize device collection
        devices: Dict[str, Dict[str, Any]] = {}
        led_entries = led_config.get("leds", [])
        
        # Create tasks for all devices
        tasks = []
        names = []
        for led in led_entries:
            name = led.get("name") or f"LED {led.get('index', '?')}"
            names.append(name)
            tasks.append(self._collect_device_state_async(led, session))
        
        # Wait for all device tasks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, result in zip(names, results):
                if isinstance(result, Exception):
                    logging.error("Failed to collect state for %s: %s", name, result)
                    devices[name] = {}
                else:
                    devices[name] = result
        
        # Build context snapshot (async)
        context_snapshot = await self._build_context_snapshot_async(session)
        
        payload = {
            "schema_version": RAW_STATE_SCHEMA_VERSION,
            "timestamp": int(time.time()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "devices": devices,
            "events": self._event_buffer.snapshot(),
            "context": context_snapshot,
        }
        
        # File I/O is still blocking but fast enough for this scale; can be offloaded if needed.
        # Ideally we'd use aiofiles, but simple atomic write is okay for now.
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

    async def _collect_device_state_async(self, led_entry: Dict[str, Any], session: aiohttp.ClientSession) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        ip = led_entry.get("ip")
        
        # These checks can run in parallel for a single device too
        coros = {}
        
        if ip:
            coros["ping"] = self._pinger.ping_async(ip)
        
        availability_entity = led_entry.get("ha_availability_entity")
        if availability_entity:
            coros["ha"] = self._ha.is_available_async(session, availability_entity)
            
        is_pihole = (led_entry.get("type") or "").lower() == "pihole"
        if is_pihole:
            coros["pihole"] = self._pihole.summary_async(session)
            
        # Run gathered tasks
        # We need to map back results. 
        # Since we have heterogenous tasks, we can just await them individually or gather.
        # Gathering is slightly better if we have multiple network calls.
        
        keys = list(coros.keys())
        values = list(coros.values())
        
        if values:
            outcomes = await asyncio.gather(*values, return_exceptions=True)
            results_map = dict(zip(keys, outcomes))
            
            if "ping" in results_map:
                res = results_map["ping"]
                if not isinstance(res, Exception):
                    reachable, rtt_ms = res
                    result["reachable"] = reachable
                    if rtt_ms is not None:
                        result["rtt_ms"] = rtt_ms
            
            if "ha" in results_map:
                res = results_map["ha"]
                if not isinstance(res, Exception) and res is not None:
                    result["ha_available"] = res

            if "pihole" in results_map:
                summary = results_map["pihole"]
                if not isinstance(summary, Exception) and summary:
                    result["qps"] = summary.get("queries_last_minute", 0) / 60.0
                    blocked = summary.get("ads_blocked_today", 0)
                    total = summary.get("dns_queries_today", 0) or 1
                    result["blocked_ratio"] = blocked / total
                    result["pihole_status"] = summary.get("status")

        event_entities = self._extract_event_entities(led_entry)
        if event_entities:
            result["events_last_window"] = self._event_buffer.count_for_entities(event_entities)
            
        return result

    # Kept synchronous version for completeness but it is no longer used by the main loop
    def _collect_device_state(self, led_entry: Dict[str, Any]) -> Dict[str, Any]:
        # Legacy/Sync implementation
        result: Dict[str, Any] = {}
        ip = led_entry.get("ip")
        if ip:
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
    
    # New async context builder
    async def _build_context_snapshot_async(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {
            "timestamp": int(time.time()),
            "daypart": self._derive_daypart(),
            "entities": {},
        }
        flags = {"occupied": False, "rain_expected": False}
        
        # Parallel fetch of context entities
        tasks = []
        for entity_id in self._context_entities:
            tasks.append(self._ha.read_state_async(session, entity_id))
            
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for entity_id, state_obj in zip(self._context_entities, results):
                if isinstance(state_obj, Exception) or not state_obj:
                    continue
                snapshot["entities"][entity_id] = {
                    "state": state_obj.get("state"),
                    "attributes": state_obj.get("attributes", {}),
                }
                self._update_flags_from_entity(flags, entity_id, state_obj)
        
        snapshot["flags"] = flags
        return snapshot

    # Legacy sync context builder
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
    home_cfg = HomeAssistantConfig(**data.get("home_assistant", {}))
    pihole_cfg = PiHoleConfig(**data.get("pihole", {}))
    ping_cfg = PingConfig(**data.get("ping", {}))
    events_cfg = EventConfig(**data.get("events", {}))
    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    poll_interval = overrides.poll_interval_seconds or float(data.get("poll_interval_seconds", 3))
    log_level = overrides.log_level or (data.get("logging", {}) or {}).get("level", "INFO")
    config = ServiceConfig(
        data_dir=data_dir,
        led_config_filename=data.get("led_config_filename", DEFAULT_LED_CONFIG_FILENAME),
        raw_state_filename=data.get("raw_state_filename", DEFAULT_RAW_STATE_FILENAME),
        events_log_filename=data.get("events_log_filename", DEFAULT_EVENTS_LOG_FILENAME),
        poll_interval_seconds=poll_interval,
        event_buffer_seconds=float(data.get("event_buffer_seconds", 10)),
        context_entities=data.get("context_entities", []) or [],
        home_assistant=home_cfg,
        pihole=pihole_cfg,
        ping=ping_cfg,
        events=events_cfg,
        log_level=log_level,
    )
    return config


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
