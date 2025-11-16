#!/usr/bin/env python3
"""Entry point for the host monitoring supervisor."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from scripts.protocol.serial_client import SerialClient
from scripts.supervisor.state_manager import StateManager

LOG = logging.getLogger("ledpanel.supervisor")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config_path = Path(__file__).resolve().parent.parent / "config" / "devices.yaml"
    state_manager = StateManager.from_config(config_path)
    serial_client = SerialClient.from_env(state_manager)

    await serial_client.start()
    await state_manager.run(serial_client)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOG.info("Supervisor interrupted by user")
