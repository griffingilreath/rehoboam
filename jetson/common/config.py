from __future__ import annotations

import os
from typing import Any, Mapping


def _expand_string(value: str) -> str:
    """Expand ${VAR} and $VAR using environment variables."""
    return os.path.expandvars(value)


def expand_env_placeholders(obj: Any) -> Any:
    """
    Recursively expand ${VAR}/$VAR placeholders in strings found within dicts/lists.
    Leaves non-strings unchanged.
    """
    if isinstance(obj, str):
        return _expand_string(obj)
    if isinstance(obj, Mapping):
        return {k: expand_env_placeholders(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand_env_placeholders(v) for v in obj]
    return obj


