"""Utilities for writing simple service health heartbeats."""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from jetson.common.json_store import atomic_write_json, load_json


@dataclass
class ServiceIdentity:
    name: str
    instance: str | None = None


class ServiceHealthTracker:
    """Append/update service heartbeat entries in service_health.json."""

    SCHEMA_VERSION = "1.0"

    def __init__(self, data_dir: Path, filename: str = "service_health.json") -> None:
        self._path = data_dir / filename
        self._host = socket.gethostname()
        self._pid = os.getpid()

    def update(self, identity: ServiceIdentity, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        payload = self._read()
        services = payload.setdefault("services", [])
        timestamp = datetime.now(timezone.utc).isoformat()
        payload.setdefault("schema_version", self.SCHEMA_VERSION)
        entry = {
            "name": identity.name,
            "instance": identity.instance,
            "host": self._host,
            "pid": self._pid,
            "status": status,
            "updated_at": timestamp,
            "details": details or {},
        }
        replaced = False
        for idx, existing in enumerate(services):
            if existing.get("name") == identity.name and existing.get("instance") == identity.instance:
                services[idx] = entry
                replaced = True
                break
        if not replaced:
            services.append(entry)
        payload["timestamp"] = timestamp
        self._write(payload)

    def mark_startup(self, identity: ServiceIdentity) -> None:
        self.update(identity, "starting")

    def mark_running(self, identity: ServiceIdentity) -> None:
        self.update(identity, "running")

    def mark_error(self, identity: ServiceIdentity, message: str) -> None:
        self.update(identity, "error", {"message": message})

    def _read(self) -> Dict[str, Any]:
        data = load_json(self._path, {})
        if not isinstance(data, dict):
            data = {}
        data.setdefault("schema_version", self.SCHEMA_VERSION)
        data.setdefault("services", [])
        return data

    def _write(self, payload: Dict[str, Any]) -> None:
        atomic_write_json(self._path, payload)
