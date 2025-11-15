"""Utilities for writing simple service health heartbeats."""
from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ServiceIdentity:
    name: str
    instance: str | None = None


class ServiceHealthTracker:
    """Append/update service heartbeat entries in service_health.json."""

    def __init__(self, data_dir: Path, filename: str = "service_health.json") -> None:
        self._path = data_dir / filename
        self._host = socket.gethostname()
        self._pid = os.getpid()

    def update(self, identity: ServiceIdentity, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        payload = self._read()
        services = payload.setdefault("services", [])
        timestamp = datetime.now(timezone.utc).isoformat()
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
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write(self, payload: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, sort_keys=False)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(serialized, encoding="utf-8")
        tmp.replace(self._path)
