"""Placeholder channel daemon tying Home Assistant events to the visualizer runtime.

Real implementation will:
- Connect to HA WebSocket or MQTT (see docs/generative_eink_visualizer_integration.md)
- Feed EntityStateEvent objects into VisualizerRuntime
- Publish semantic channel payloads via file/MQTT/HTTP

This stub keeps the module importable and documents the intended API surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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

    def handle_event(self, event: EntityStateEvent) -> None:
        channels = self._runtime.handle_event(event)
        if channels is None:
            return
        self._publisher.publish(channels)

    def run_forever(self) -> None:  # pragma: no cover - placeholder
        raise NotImplementedError(
            "Wire this up to Home Assistant per docs/generative_eink_visualizer_integration.md"
        )
