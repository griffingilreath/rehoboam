from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from .config.models import EntitySpec, FeatureDefinition, FeatureType
from .types import EntityStateEvent, FeatureSnapshot


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class _Smoother:
    constant: float
    value: float | None = None
    last_timestamp: datetime | None = None

    def update(self, sample: float, timestamp: datetime) -> float:
        if self.value is None or self.last_timestamp is None:
            self.value = sample
        else:
            delta = max((timestamp - self.last_timestamp).total_seconds(), 0.0)
            if self.constant <= 0:
                alpha = 1.0
            else:
                alpha = min(1.0, delta / self.constant)
            self.value = self.value + alpha * (sample - self.value)
        self.last_timestamp = timestamp
        return self.value


class FeatureSpace:
    """Maintains a normalized feature dictionary derived from HA entity events."""

    def __init__(self, entities: Iterable[EntitySpec]):
        self._entity_map = {spec.entity_id: spec for spec in entities}
        self._feature_defs = {
            feature.feature_id: feature
            for spec in entities
            for feature in spec.features.values()
        }
        self._values: dict[str, FeatureSnapshot] = {}
        self._event_windows: dict[str, deque[datetime]] = defaultdict(deque)
        self._smoothers: dict[str, _Smoother] = {}

    def process_event(self, event: EntityStateEvent) -> list[FeatureSnapshot]:
        spec = self._entity_map.get(event.entity_id)
        if not spec:
            return []
        timestamp = event.timestamp()
        snapshots: list[FeatureSnapshot] = []
        for feature in spec.features.values():
            evaluation = self._evaluate_feature(feature, event, timestamp)
            if evaluation is None:
                continue
            value, raw = evaluation
            value = self._apply_smoothing(feature, value, timestamp)
            snapshot = FeatureSnapshot(
                feature_id=feature.feature_id,
                value=value,
                raw_value=raw,
                updated_at=timestamp,
                metadata={"entity_id": spec.entity_id},
            )
            self._values[feature.feature_id] = snapshot
            snapshots.append(snapshot)
        return snapshots

    def set_feature(self, feature_id: str, value: float, *, timestamp: datetime | None = None) -> None:
        """Force-set a feature value (useful for tests).

        The value is clamped to [0, 1] to keep downstream math stable.
        """

        clamped = max(0.0, min(1.0, value))
        snapshot = FeatureSnapshot(
            feature_id=feature_id,
            value=clamped,
            raw_value=value,
            updated_at=timestamp,
        )
        self._values[feature_id] = snapshot

    def get(self, feature_id: str) -> float:
        snapshot = self._values.get(feature_id)
        return snapshot.value if snapshot else 0.0

    def as_dict(self) -> dict[str, float]:
        return {feature_id: snapshot.value for feature_id, snapshot in self._values.items()}

    def _evaluate_feature(
        self, feature: FeatureDefinition, event: EntityStateEvent, timestamp: datetime
    ) -> tuple[float, float] | None:
        if feature.type == "numeric":
            raw = _to_float(event.state)
            if raw is None:
                return None
            value = self._normalize(feature, raw)
            return value, raw
        if feature.type == "attribute":
            if not event.attributes or feature.attribute is None:
                return None
            raw = _to_float(event.attributes.get(feature.attribute))
            if raw is None:
                return None
            value = self._normalize(feature, raw)
            return value, raw
        if feature.type == "binary":
            truthy = str(event.state).lower() in {"on", "true", "open", "playing"}
            raw = feature.present_value if truthy else feature.absent_value
            value = max(0.0, min(1.0, raw))
            return value, raw
        if feature.type == "state_enum":
            if not feature.mapping:
                return None
            key = str(event.state)
            raw = feature.mapping.get(key)
            if raw is None:
                return None
            value = max(0.0, min(1.0, raw)) if not feature.normalize else feature.normalize.normalize(raw)
            return value, raw
        if feature.type == "event_rate":
            return self._evaluate_event_rate(feature, event, timestamp)
        return None

    def _normalize(self, feature: FeatureDefinition, raw: float) -> float:
        if feature.normalize:
            return feature.normalize.normalize(raw)
        return raw

    def _evaluate_event_rate(
        self, feature: FeatureDefinition, event: EntityStateEvent, timestamp: datetime
    ) -> tuple[float, float]:
        window_seconds = feature.window_seconds or 600
        max_events = feature.max_events or 10
        target_state = feature.event_state or "on"
        deque_window = self._event_windows[feature.feature_id]

        state_matches = str(event.state).lower() == target_state.lower()
        if state_matches:
            deque_window.append(timestamp)
        cutoff = timestamp - timedelta(seconds=window_seconds)
        while deque_window and deque_window[0] < cutoff:
            deque_window.popleft()
        raw_count = float(len(deque_window))
        value = min(raw_count / max_events, 1.0)
        return value, raw_count

    def _apply_smoothing(
        self, feature: FeatureDefinition, value: float, timestamp: datetime
    ) -> float:
        if not feature.smoothing_seconds:
            return value
        smoother = self._smoothers.get(feature.feature_id)
        if not smoother:
            smoother = _Smoother(constant=float(feature.smoothing_seconds))
            self._smoothers[feature.feature_id] = smoother
        return smoother.update(value, timestamp)
