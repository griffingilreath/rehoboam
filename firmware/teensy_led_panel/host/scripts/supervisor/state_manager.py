"""Supervises monitors and decides which commands to send to the Teensy."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

LOG = logging.getLogger("ledpanel.state")


@dataclass
class DeviceConfig:
    name: str
    kind: str
    target: str
    priority: str = "normal"


class StateManager:
    def __init__(self, devices: Dict[str, DeviceConfig]) -> None:
        self._devices = devices
        self._serial = None
        self._base_state = "STARTUP"
        self._alarm_active: Optional[str] = None
        self._notification_pending: Optional[str] = None

    @classmethod
    def from_config(cls, config_path: Path) -> "StateManager":
        # TODO: Parse YAML once written; for now return empty config
        LOG.debug("Loading config from %s", config_path)
        return cls(devices={})

    async def on_serial_ready(self, serial_client) -> None:
        self._serial = serial_client
        await self._serial.write_line("READY")

    async def on_serial_lost(self) -> None:
        LOG.warning("Serial connection lost; entering error watchdog")
        self._serial = None

    async def run(self, serial_client) -> None:
        self._serial = serial_client
        await self._ensure_base_state("LIVE")
        while True:
            await asyncio.sleep(30)
            await self._serial.write_line("PING")

    async def handle_frame(self, frame: str) -> None:
        LOG.debug("Received frame: %s", frame)
        if frame.startswith("ACK:"):
            return
        if frame.startswith("ERR:"):
            LOG.error("Teensy reported error: %s", frame)

    async def activate_alarm(self, alarm_id: str) -> None:
        self._alarm_active = alarm_id
        await self._serial.write_line(f"ALARM:{alarm_id}:ON")

    async def clear_alarm(self, alarm_id: str) -> None:
        if self._alarm_active == alarm_id:
            self._alarm_active = None
        await self._serial.write_line(f"ALARM:{alarm_id}:OFF")

    async def send_notification(self, notification_type: str, ttl_ms: int = 5000) -> None:
        self._notification_pending = notification_type
        await self._serial.write_line(f"NOTIFY:{notification_type}:{ttl_ms}")

    async def _ensure_base_state(self, state: str) -> None:
        if state == self._base_state:
            return
        await self._serial.write_line(f"STATE:{state}")
        self._base_state = state
