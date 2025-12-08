from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import yaml

from .models import ChannelDefinition, EntitySpec, VisualizerConfig


def _ensure_sequence(payload: object, default_key: str) -> Sequence[dict]:
    if isinstance(payload, dict) and default_key in payload:
        payload = payload[default_key]
    if not isinstance(payload, Sequence):
        raise ValueError(f"Expected a list of {default_key}, got {type(payload)!r}")
    return payload  # type: ignore[return-value]


def load_entities(path: str | Path) -> tuple[EntitySpec, ...]:
    data = yaml.safe_load(Path(path).read_text())
    items = _ensure_sequence(data, "entities")
    return tuple(EntitySpec.from_dict(item) for item in items)


def load_channels(path: str | Path) -> tuple[ChannelDefinition, ...]:
    data = yaml.safe_load(Path(path).read_text())
    items = _ensure_sequence(data, "channels")
    return tuple(ChannelDefinition.from_dict(item) for item in items)


def load_config(entities_path: str | Path, channels_path: str | Path) -> VisualizerConfig:
    entities = load_entities(entities_path)
    channels = load_channels(channels_path)
    return VisualizerConfig.from_iterables(entities, channels)
