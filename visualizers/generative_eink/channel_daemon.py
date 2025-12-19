"""Placeholder channel daemon tying Home Assistant events to the visualizer runtime.

Real implementation will:
- Connect to HA WebSocket or MQTT (see docs/generative_eink_visualizer_integration.md)
- Feed EntityStateEvent objects into VisualizerRuntime
- Publish semantic channel payloads via file/MQTT/HTTP

This stub keeps the module importable and documents the intended API surface.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

import aiohttp

from .config import loaders as config_loaders
from .runtime import VisualizerRuntime
from .types import EntityStateEvent


class ChannelPublisher(Protocol):
    """Interface for transporting channel payloads elsewhere."""

    def publish(self, payload: dict[str, float]) -> None:
        ...  # pragma: no cover - protocol


@dataclass(slots=True)
class ChannelDaemonConfig:
    entities_path: Path
    channels_path: Path
    poll_interval: float = 5.0


class ChannelDaemon:
    """Skeletal daemon showing where HA ingestion + publishing will sit."""

    def __init__(self, config: ChannelDaemonConfig, publisher: ChannelPublisher):
        self._config = config
        self._publisher = publisher
        viz_config = config_loaders.load_config(config.entities_path, config.channels_path)
        self._runtime = VisualizerRuntime.from_config(viz_config)
        self._log = logging.getLogger("generative_eink.daemon")

    def handle_event(self, event: EntityStateEvent) -> None:
        channels = self._runtime.handle_event(event)
        if channels is None:
            return
        self._publisher.publish(channels)

    async def run_forever(self, ha_base_url: str, ha_token: str) -> None:
        """Connect to HA WebSocket and process events indefinitely."""
        # Normalize URL to websocket
        if ha_base_url.startswith("http"):
             ws_url = ha_base_url.replace("http", "ws", 1) + "/api/websocket"
        else:
             # Assume ws provided or fallback
             ws_url = ha_base_url
        
        if "websocket" not in ws_url:
            ws_url = ws_url.rstrip("/") + "/api/websocket"

        self._log.info("Starting Channel Daemon (WS: %s)", ws_url)

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(ws_url) as ws:
                        # Authenticate
                        await ws.send_json({"type": "auth", "access_token": ha_token})
                        auth_resp = await ws.receive_json()
                        
                        if auth_resp.get("type") != "auth_ok":
                            self._log.error("HA Auth failed: %s", auth_resp)
                            # Fatal error, backoff long time or exit? 
                            # We'll backoff to avoid tight loop
                            await asyncio.sleep(60)
                            continue

                        self._log.info("Authenticated to Home Assistant")

                        # Subscribe
                        await ws.send_json({
                            "id": 1,
                            "type": "subscribe_events",
                            "event_type": "state_changed"
                        })
                        
                        # Loop
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = msg.json()
                                except json.JSONDecodeError:
                                    continue
                                
                                if data.get("type") == "event":
                                    self._process_ha_event(data["event"])
                                    
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                self._log.error("WebSocket connection closed with error %s", ws.exception())
                                break
            except Exception as e:
                self._log.error("Connection error: %s. Retrying in 5s...", e)
                await asyncio.sleep(5)

    def _process_ha_event(self, event_data: dict) -> None:
        data = event_data.get("data", {})
        entity_id = data.get("entity_id")
        new_state = data.get("new_state")
        
        if not entity_id or not new_state:
            return

        # Parse timestamp
        last_changed = None
        if ts_str := new_state.get("last_changed"):
             try:
                 last_changed = datetime.fromisoformat(ts_str)
             except ValueError:
                 pass

        event = EntityStateEvent(
            entity_id=entity_id,
            state=new_state.get("state"),
            attributes=new_state.get("attributes"),
            last_changed=last_changed
        )
        
        self.handle_event(event)
