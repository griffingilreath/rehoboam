"""Shared LED health/activity enumerations and helpers."""
from __future__ import annotations

from enum import IntEnum
from typing import Dict


class HealthCode(IntEnum):
    OFF = 0
    OK = 1
    WARNING = 2
    ERROR = 3
    UNKNOWN = 4

    @classmethod
    def default_map(cls) -> Dict[str, int]:
        return {name: member.value for name, member in cls.__members__.items()}


class ActivityType(IntEnum):
    NONE = 0
    LIGHT_CHANGE = 1
    BLIND_MOVE = 2
    DNS_QUERIES = 3
    GENERIC_EVENT = 4

    @classmethod
    def default_map(cls) -> Dict[str, int]:
        # canonical_state uses lowercase activity type names
        return {name.lower(): member.value for name, member in cls.__members__.items()}


def merge_health_map(overrides: Dict[str, int] | None) -> Dict[str, int]:
    """Return a case-insensitive health code map, overriding defaults as needed."""
    mapping = HealthCode.default_map()
    if overrides:
        for key, value in overrides.items():
            mapping[str(key).upper()] = int(value)
    return mapping


def merge_activity_map(overrides: Dict[str, int] | None) -> Dict[str, int]:
    """Return a lowercase activity type map, overriding defaults as needed."""
    mapping = ActivityType.default_map()
    if overrides:
        for key, value in overrides.items():
            mapping[str(key).lower()] = int(value)
    return mapping

