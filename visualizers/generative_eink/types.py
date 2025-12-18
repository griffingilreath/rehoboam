from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping


@dataclass(frozen=True, slots=True)
class EntityStateEvent:
    """Represents a Home Assistant-style state_changed event."""

    entity_id: str
    state: Any
    attributes: Mapping[str, Any] | None = None
    last_changed: datetime | None = None

    def timestamp(self) -> datetime:
        """Return the event timestamp, defaulting to *now* in UTC."""

        return self.last_changed or datetime.now(timezone.utc)


@dataclass(slots=True)
class FeatureSnapshot:
    """Captures the evaluated value of a single feature."""

    feature_id: str
    value: float
    raw_value: float | None = None
    updated_at: datetime | None = None
    metadata: MutableMapping[str, Any] | None = None
