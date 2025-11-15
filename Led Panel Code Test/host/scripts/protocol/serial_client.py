"""Async serial client managing USB communication with the Teensy."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

import serial
import serial.asyncio

LOG = logging.getLogger("ledpanel.serial")


@dataclass
class SerialSettings:
    port: str
    baudrate: int = 115200
    reconnect_delay: float = 2.0


class SerialClient:
    def __init__(self, settings: SerialSettings, state_manager) -> None:
        self._settings = settings
        self._state_manager = state_manager
        self._reader: Optional[serial.asyncio.SerialTransport] = None
        self._writer: Optional[serial.asyncio.SerialTransport] = None

    @classmethod
    def from_env(cls, state_manager):
        port = os.environ.get("LED_PANEL_PORT", "/dev/ttyACM0")
        baud = int(os.environ.get("LED_PANEL_BAUD", "115200"))
        settings = SerialSettings(port=port, baudrate=baud)
        return cls(settings, state_manager)

    async def start(self) -> None:
        await self._connect()

    async def _connect(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                LOG.info("Connecting to serial port %s", self._settings.port)
                self._reader, self._writer = await serial.asyncio.open_serial_connection(
                    url=self._settings.port,
                    baudrate=self._settings.baudrate,
                )
                LOG.info("Serial connection established")
                asyncio.create_task(self._read_loop())
                await self._state_manager.on_serial_ready(self)
                return
            except (serial.SerialException, OSError) as exc:
                LOG.warning("Serial connection failed: %s", exc)
                await asyncio.sleep(self._settings.reconnect_delay)

    async def write_line(self, payload: str) -> None:
        if not self._writer:
            LOG.debug("Serial writer not ready; dropping payload %s", payload)
            return
        line = f"{payload}\n".encode("utf-8")
        self._writer.write(line)

    async def _read_loop(self) -> None:
        assert self._reader is not None
        reader = self._reader
        while True:
            try:
                line = await reader.readline()
            except (serial.SerialException, OSError) as exc:
                LOG.error("Serial read error: %s", exc)
                await self._state_manager.on_serial_lost()
                await self._connect()
                return

            if not line:
                LOG.warning("Serial connection closed by peer")
                await self._state_manager.on_serial_lost()
                await self._connect()
                return

            text = line.decode("utf-8", errors="ignore").strip()
            if not text:
                continue

            await self._state_manager.handle_frame(text)
