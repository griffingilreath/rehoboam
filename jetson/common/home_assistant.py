"""Shared Home Assistant client utilities."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import aiohttp
import requests


@dataclass
class HomeAssistantConfig:
    base_url: str
    token: str
    timeout_seconds: float = 10.0
    verify_ssl: bool = True
    availability_states: Dict[str, bool] | None = None

    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")


class HomeAssistantClient:
    def __init__(self, config: HomeAssistantConfig) -> None:
        self._config = config
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
        })
        self._session.verify = config.verify_ssl
        self._base_url = config.normalized_base_url()
        self._availability_states = config.availability_states or {"on": True, "off": False}

    def read_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Synchronous fetch of entity state."""
        url = f"{self._base_url}/api/states/{entity_id}"
        try:
            response = self._session.get(url, timeout=self._config.timeout_seconds)
        except requests.RequestException as exc:
            logging.warning("HA request failed for %s: %s", entity_id, exc)
            return None
        if response.status_code == 404:
            logging.debug("HA entity %s not found", entity_id)
            return None
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            logging.error("HA error for %s: %s", entity_id, exc)
            return None
        return response.json()

    async def read_state_async(self, session: aiohttp.ClientSession, entity_id: str) -> Optional[Dict[str, Any]]:
        """Asynchronous fetch of entity state."""
        url = f"{self._base_url}/api/states/{entity_id}"
        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "Content-Type": "application/json",
        }
        ssl_context = None if self._config.verify_ssl else False
        try:
            async with session.get(url, headers=headers, ssl=ssl_context, timeout=self._config.timeout_seconds) as response:
                if response.status == 404:
                    logging.debug("HA entity %s not found", entity_id)
                    return None
                if response.status >= 400:
                    logging.error("HA error for %s: %s", entity_id, response.status)
                    return None
                return await response.json()
        except asyncio.TimeoutError:
            logging.warning("HA request timed out for %s", entity_id)
            return None
        except Exception as exc:
            logging.warning("HA request failed for %s: %s", entity_id, exc)
            return None

    def is_available(self, entity_id: str) -> Optional[bool]:
        state = self.read_state(entity_id)
        return self._check_availability(state)

    async def is_available_async(self, session: aiohttp.ClientSession, entity_id: str) -> Optional[bool]:
        state = await self.read_state_async(session, entity_id)
        return self._check_availability(state)

    def _check_availability(self, state: Optional[Dict[str, Any]]) -> Optional[bool]:
        if not state:
            return None
        value = state.get("state")
        if isinstance(value, str):
            normalized = value.lower()
            if normalized in self._availability_states:
                return bool(self._availability_states[normalized])
        return None

    def websocket_url(self) -> str:
        """Derive the WebSocket URL from the HTTP base URL."""
        parsed = urlparse(self._base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Home Assistant base_url must be http or https")
        scheme = "ws" if parsed.scheme == "http" else "wss"
        netloc = parsed.netloc
        return f"{scheme}://{netloc}/api/websocket"
