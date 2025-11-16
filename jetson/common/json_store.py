"""Shared helpers for JSON IO (with atomic writes)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON data from *path*; return *default* if missing or invalid."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    """Atomically write JSON to *path* using a temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as tmp:
        json.dump(payload, tmp, indent=indent)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_name = Path(tmp.name)
    temp_name.replace(path)
