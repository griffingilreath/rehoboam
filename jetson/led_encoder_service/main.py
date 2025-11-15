#!/usr/bin/env python3
"""Stream canonical LED state to the Teensy over serial."""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import serial
import yaml

from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity


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

    def run(self) -> None:
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


def load_service_config(path: Path) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = ServiceConfig(
        data_dir=Path(data.get("data_dir", "./data")).expanduser().resolve(),
        canonical_state_filename=data.get("canonical_state_filename", DEFAULT_CANONICAL_FILENAME),
        serial_device=data.get("serial_device", "/dev/ttyACM0"),
        baud_rate=int(data.get("baud_rate", 115200)),
        frame_interval_seconds=float(data.get("frame_interval_seconds", 0.2)),
        health_code_map={k.upper(): int(v) for k, v in (data.get("health_code_map") or {}).items()},
        activity_type_map={str(k).lower(): int(v) for k, v in (data.get("activity_type_map") or {}).items()},
        log_level=(data.get("logging", {}) or {}).get("level", "INFO"),
    )
    if "UNKNOWN" not in config.health_code_map:
        config.health_code_map["UNKNOWN"] = 4
    if "none" not in config.activity_type_map:
        config.activity_type_map["none"] = 0
    if "generic_event" not in config.activity_type_map:
        config.activity_type_map["generic_event"] = max({"none": 0, **config.activity_type_map}.values())
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Encode canonical LED state to serial frames")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Override configured log level",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print frames to stdout instead of sending to serial",
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
    logging.info("Starting led_encoder_service using %s", service_config.serial_device)
    service = LedEncoderService(service_config, dry_run=args.dry_run)
    signal.signal(signal.SIGTERM, service.request_stop)
    signal.signal(signal.SIGINT, service.request_stop)
    service.run()


if __name__ == "__main__":
    main()
