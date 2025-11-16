#!/usr/bin/env python3
"""Stream canonical LED state to the Teensy over serial."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import serial
import yaml

from jetson.common.led_codes import merge_activity_map, merge_health_map
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service


DEFAULT_CONFIG_PATH = "jetson/led_encoder_service/config.yaml"
DEFAULT_CANONICAL_FILENAME = "canonical_state.json"


@dataclass
class ServiceConfig:
    data_dir: Path
    canonical_state_filename: str
    serial_device: str
    baud_rate: int
    frame_interval_seconds: float
    health_code_map: Dict[str, int]
    activity_type_map: Dict[str, int]
    log_level: str = "INFO"

    @property
    def canonical_path(self) -> Path:
        return self.data_dir / self.canonical_state_filename


class LedEncoderService:
    def __init__(self, config: ServiceConfig, dry_run: bool = False) -> None:
        self._config = config
        self._serial: Optional[serial.Serial] = None
        self._stop_requested = False
        self._last_frame_payload: Optional[str] = None
        self._dry_run = dry_run
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="led_encoder_service")

    def request_stop(self, *_: Any) -> None:
        logging.info("Stop requested; closing serial port")
        self._stop_requested = True
        self._close_serial()

    def run(self, run_once: bool = False) -> None:
        next_send = 0.0
        self._health.mark_running(self._identity)
        while not self._stop_requested:
            now = time.monotonic()
            if now < next_send:
                time.sleep(max(0.0, next_send - now))
                continue
            next_send = now + self._config.frame_interval_seconds
            try:
                self._send_frame_if_needed()
            except Exception:
                logging.exception("Failed to send LED frame")
                self._health.mark_error(self._identity, "frame send failed")
                time.sleep(self._config.frame_interval_seconds)

    def _send_frame_if_needed(self) -> None:
        canonical_state = self._load_canonical_state()
        if not canonical_state:
            logging.debug("Canonical state missing or empty; skipping frame")
            return
        frame = self._build_frame(canonical_state)
        serialized = json.dumps(frame, separators=(",", ":"))
        if serialized == self._last_frame_payload:
            logging.debug("Frame unchanged; not writing to serial")
            return
        if self._dry_run:
            print(serialized)
        else:
            self._ensure_serial_open()
            if not self._serial:
                logging.warning("Serial device unavailable; dropping frame")
                return
            self._serial.write(serialized.encode("utf-8"))
            self._serial.write(b"\n")
            self._serial.flush()
        self._last_frame_payload = serialized
        logging.info("Sent frame %s with %d LEDs", frame.get("frame_id"), len(frame.get("leds", [])))
        self._health.mark_running(self._identity)

    def _build_frame(self, canonical_state: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = canonical_state.get("timestamp", int(time.time()))
        leds = []
        for led_entry in canonical_state.get("leds", []):
            leds.append({
                "i": int(led_entry.get("index", 0)),
                "h": self._map_health(led_entry.get("health")),
                "a": round(float(led_entry.get("activity_level", 0.0)), 3),
                "t": self._map_activity_type(led_entry.get("activity_type")),
            })
        return {
            "frame_id": timestamp,
            "timestamp": timestamp,
            "leds": leds,
        }

    def _map_health(self, health: Optional[str]) -> int:
        if not health:
            return self._config.health_code_map.get("UNKNOWN", 4)
        return self._config.health_code_map.get(health.upper(), self._config.health_code_map.get("UNKNOWN", 4))

    def _map_activity_type(self, activity: Optional[str]) -> int:
        if not activity:
            return self._config.activity_type_map.get("none", 0)
        key = activity.lower()
        return self._config.activity_type_map.get(key, self._config.activity_type_map.get("generic_event", 4))

    def _load_canonical_state(self) -> Optional[Dict[str, Any]]:
        path = self._config.canonical_path
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging.error("Invalid JSON in %s: %s", path, exc)
            return None

    def _ensure_serial_open(self) -> None:
        if self._dry_run:
            return
        if self._serial and self._serial.is_open:
            return
        self._close_serial()
        try:
            self._serial = serial.Serial(
                self._config.serial_device,
                self._config.baud_rate,
                timeout=1,
            )
            logging.info("Opened serial device %s @ %d", self._config.serial_device, self._config.baud_rate)
        except serial.SerialException as exc:
            logging.error("Unable to open serial device %s: %s", self._config.serial_device, exc)
            self._serial = None

    def _close_serial(self) -> None:
        if self._dry_run:
            return
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
                logging.info("Closed serial device")
            except serial.SerialException as exc:
                logging.warning("Error closing serial device: %s", exc)
        self._serial = None


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = overrides or RunnerOverrides()
    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    log_level = overrides.log_level or (data.get("logging", {}) or {}).get("level", "INFO")
    config = ServiceConfig(
        data_dir=data_dir,
        canonical_state_filename=data.get("canonical_state_filename", DEFAULT_CANONICAL_FILENAME),
        serial_device=data.get("serial_device", "/dev/ttyACM0"),
        baud_rate=int(data.get("baud_rate", 115200)),
        frame_interval_seconds=float(data.get("frame_interval_seconds", 0.2)),
        health_code_map=merge_health_map(data.get("health_code_map")),
        activity_type_map=merge_activity_map(data.get("activity_type_map")),
        log_level=log_level,
    )
    return config


def main() -> None:
    def _add_extra_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print frames instead of sending them over serial",
        )

    def _create_service(config: ServiceConfig, args: argparse.Namespace) -> LedEncoderService:
        logging.info("LED encoder using %s", config.serial_device)
        return LedEncoderService(config, dry_run=args.dry_run)

    run_service(
        service_name="led_encoder_service",
        description="Encode canonical LED state to serial frames",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
        add_arguments=_add_extra_args,
        supports_once=False,
        supports_interval_override=False,
    )


if __name__ == "__main__":
    main()
