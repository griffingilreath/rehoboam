from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterable, Literal, Mapping, MutableMapping

FeatureType = Literal["numeric", "binary", "attribute", "state_enum", "event_rate"]
CurveType = Literal["linear", "smoothstep", "ease_in", "ease_out"]


@dataclass(slots=True)
class NormalizeSpec:
    """Defines how to normalize a numeric feature."""

    min: float
    max: float
    clamp: bool = True

    def normalize(self, value: float) -> float:
        span = self.max - self.min
        if span == 0:
            return 0.0
        normalized = (value - self.min) / span
        if self.clamp:
            return max(0.0, min(1.0, normalized))
        return normalized

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NormalizeSpec":
        return cls(
            min=float(payload.get("min", 0.0)),
            max=float(payload.get("max", 1.0)),
            clamp=bool(payload.get("clamp", True)),
        )


@dataclass(slots=True)
class FeatureDefinition:
    """Maps a Home Assistant entity to a normalized feature."""

    feature_id: str
    type: FeatureType
    normalize: NormalizeSpec | None = None
    attribute: str | None = None
    mapping: Mapping[str, float] | None = None
    window_seconds: int | None = None
    max_events: int | None = None
    event_state: str | None = None
    present_value: float = 1.0
    absent_value: float = 0.0
    smoothing_seconds: int | None = None

    @classmethod
    def from_dict(cls, feature_id: str, payload: Mapping[str, Any]) -> "FeatureDefinition":
        normalize = payload.get("normalize")
        mapping = payload.get("mapping")
        return cls(
            feature_id=feature_id,
            type=payload.get("type", "numeric"),
            normalize=NormalizeSpec.from_dict(normalize) if normalize else None,
            attribute=payload.get("attribute"),
            mapping=mapping or None,
            window_seconds=payload.get("window_seconds"),
            max_events=payload.get("max_events"),
            event_state=payload.get("event_state"),
            present_value=float(payload.get("present_value", 1.0)),
            absent_value=float(payload.get("absent_value", 0.0)),
            smoothing_seconds=payload.get("smoothing_seconds"),
        )


@dataclass(slots=True)
class EntitySpec:
    """Configures how to extract features from a Home Assistant entity."""

    entity_id: str
    features: Mapping[str, FeatureDefinition]
    area: str | None = None
    description: str | None = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EntitySpec":
        entity_id = payload["id"]
        feature_payload = payload.get("features", {})
        features = {
            feature_id: FeatureDefinition.from_dict(feature_id, spec)
            for feature_id, spec in feature_payload.items()
        }
        return cls(
            entity_id=entity_id,
            features=features,
            area=payload.get("area"),
            description=payload.get("description"),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(slots=True)
class ChannelTerm:
    feature_id: str
    weight: float = 1.0
    curve: CurveType = "linear"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ChannelTerm":
        return cls(
            feature_id=payload["feature"],
            weight=float(payload.get("weight", 1.0)),
            curve=payload.get("curve", "linear"),
        )


@dataclass(slots=True)
class ChannelDefinition:
    channel_id: str
    terms: tuple[ChannelTerm, ...]
    bias: float = 0.0
    clamp: tuple[float, float] = (0.0, 1.0)
    description: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ChannelDefinition":
        terms_payload = payload.get("formula") or payload.get("terms") or []
        terms = tuple(ChannelTerm.from_dict(term) for term in terms_payload)
        return cls(
            channel_id=payload["id"],
            terms=terms,
            bias=float(payload.get("bias", 0.0)),
            clamp=tuple(payload.get("clamp", (0.0, 1.0))),
            description=payload.get("description"),
        )


@dataclass(slots=True)
class VisualizerConfig:
    """Bundle of entity and channel specifications."""

    entities: tuple[EntitySpec, ...]
    channels: tuple[ChannelDefinition, ...]

    @classmethod
    def from_iterables(
        cls, entities: Iterable[EntitySpec], channels: Iterable[ChannelDefinition]
    ) -> "VisualizerConfig":
        return cls(tuple(entities), tuple(channels))
