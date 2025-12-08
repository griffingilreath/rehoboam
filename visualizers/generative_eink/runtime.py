from __future__ import annotations

from typing import Iterable

from .channel_space import ChannelSpace
from .config.models import ChannelDefinition, EntitySpec, VisualizerConfig
from .feature_space import FeatureSpace
from .types import EntityStateEvent


class VisualizerRuntime:
    """High-level façade that tracks features and exposes semantic channels."""

    def __init__(self, entities: Iterable[EntitySpec], channels: Iterable[ChannelDefinition]):
        self._feature_space = FeatureSpace(entities)
        self._channel_space = ChannelSpace(tuple(channels))

    @classmethod
    def from_config(cls, config: VisualizerConfig) -> "VisualizerRuntime":
        return cls(config.entities, config.channels)

    def handle_event(self, event: EntityStateEvent) -> dict[str, float] | None:
        """Process an entity event and return updated channel values.

        Returns None when the event does not affect any configured features.
        """

        snapshots = self._feature_space.process_event(event)
        if not snapshots:
            return None
        features = self._feature_space.as_dict()
        return self._channel_space.evaluate(features)

    def set_feature(self, feature_id: str, value: float) -> None:
        """Directly set a normalized feature value (useful for simulations/tests)."""

        self._feature_space.set_feature(feature_id, value)

    def get_features(self) -> dict[str, float]:
        return self._feature_space.as_dict()

    def get_channels(self) -> dict[str, float]:
        features = self._feature_space.as_dict()
        return self._channel_space.evaluate(features)
