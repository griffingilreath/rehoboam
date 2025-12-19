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
import glob
from typing import Any, Dict, Optional

import serial
import yaml

from jetson.common.led_codes import merge_activity_map, merge_health_map
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service


DEFAULT_CONFIG_PATH = str(Path(__file__).parent / "config.yaml")
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
        self._last_frame_payload: Optional[bytes] = None
        self._dry_run = dry_run
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="led_encoder_service")
        self._last_mtime: float = 0.0
        self._cached_canonical_state: Optional[Dict[str, Any]] = None

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
        
        # Build binary frame instead of JSON
        # Frame format: START_MARKER (1) + 16 * (Health(1) + ActivityLevel(1) + ActivityType(1)) + END_MARKER (1)
        # Total: 50 bytes
        frame_bytes = self._build_binary_frame(canonical_state)
        
        if frame_bytes == self._last_frame_payload:
            logging.debug("Frame unchanged; not writing to serial")
            return

        if self._dry_run:
            print(f"Binary frame ({len(frame_bytes)} bytes): {frame_bytes.hex()}")
        else:
            self._ensure_serial_open()
            if not self._serial:
                logging.warning("Serial device unavailable; dropping frame")
                return
            self._serial.write(frame_bytes)
            self._serial.flush()
        
        self._last_frame_payload = frame_bytes
        logging.info("Sent binary frame (%d bytes)", len(frame_bytes))
        self._health.mark_running(self._identity)

    def _build_binary_frame(self, canonical_state: Dict[str, Any]) -> bytes:
        # Sort LEDs by index to ensure correct order
        leds_list = canonical_state.get("leds", [])
        # Create a map for easy lookup
        led_map = {int(led.get("index", -1)): led for led in leds_list}
        
        buffer = bytearray()
        buffer.append(0xBE)  # START_MARKER
        
        for i in range(16):  # LED_COUNT = 16
            led = led_map.get(i, {})
            
            # Health (uint8)
            health_str = led.get("health")
            health_code = self._map_health(health_str)
            buffer.append(health_code)
            
            # Activity Level (uint8, scaled 0-255 from 0.0-1.0)
            activity_level = float(led.get("activity_level", 0.0))
            activity_byte = min(255, max(0, int(activity_level * 255)))
            buffer.append(activity_byte)
            
            # Activity Type (uint8)
            activity_type_str = led.get("activity_type")
            type_code = self._map_activity_type(activity_type_str)
            buffer.append(type_code)
            
        buffer.append(0xED)  # END_MARKER
        return bytes(buffer)

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
            stat = path.stat()
            if stat.st_mtime > self._last_mtime:
                self._cached_canonical_state = json.loads(path.read_text(encoding="utf-8"))
                self._last_mtime = stat.st_mtime
                logging.debug("Loaded canonical state from disk (mtime=%s)", self._last_mtime)
            return self._cached_canonical_state
        except json.JSONDecodeError as exc:
            logging.error("Invalid JSON in %s: %s", path, exc)
            return self._cached_canonical_state
        except OSError as exc:
            logging.error("IO error reading %s: %s", path, exc)
            return self._cached_canonical_state

    def _ensure_serial_open(self) -> None:
        if self._dry_run:
            return
        if self._serial and self._serial.is_open:
            return
        self._close_serial()
        try:
            device: Optional[str] = self._config.serial_device
            if device == "auto":
                device = self._auto_detect_serial_device()
            if device is None:
                logging.error("No serial device detected for Teensy (auto mode); skipping open")
                return
            self._serial = serial.Serial(
                device,
                self._config.baud_rate,
                timeout=1,
            )
            logging.info("Opened serial device %s @ %d", device, self._config.baud_rate)
        except serial.SerialException as exc:
            logging.error("Unable to open serial device %s: %s", self._config.serial_device, exc)
            self._serial = None

    @staticmethod
    def _auto_detect_serial_device() -> Optional[str]:
        """Best-effort detection of a Teensy serial device."""
        # Prefer /dev/serial/by-id entries mentioning Teensy
        by_id = glob.glob("/dev/serial/by-id/*Teensy*") + glob.glob("/dev/serial/by-id/*teensy*")
        if by_id:
            try:
                real = Path(by_id[0]).resolve()
                return str(real)
            except OSError:
                return by_id[0]
        # Fallback to first ttyACM* or ttyUSB*
        for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*"):
            matches = sorted(glob.glob(pattern))
            if matches:
                return matches[0]
        return None

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
