#!/usr/bin/env python3
"""Expose canonical LED state via FastAPI."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from jetson.common.service_runner import RunnerOverrides, run_service
from jetson.common.json_store import atomic_write_json


DEFAULT_CONFIG_PATH = "jetson/api_service/config.yaml"
DEFAULT_LED_CONFIG_FILENAME = "led_config.json"
DEFAULT_CANONICAL_FILENAME = "canonical_state.json"
DEFAULT_HISTORY_FILENAME = "history.json"
DEFAULT_HEALTH_FILENAME = "service_health.json"
DEFAULT_DIVERGENCE_FILENAME = "divergence.json"
<<<<<<< HEAD
DEFAULT_COGNITION_FILENAME = "cognition.json"
DEFAULT_AI_RECOMMENDATIONS_FILENAME = "ai_recommendations.json"
DEFAULT_FEEDBACK_FILENAME = "feedback.json"
=======
DEFAULT_RECOMMENDATIONS_STATE_FILENAME = "recommendations_state.json"
>>>>>>> origin/main


@dataclass
class ServiceConfig:
    data_dir: Path
    led_config_filename: str = DEFAULT_LED_CONFIG_FILENAME
    canonical_state_filename: str = DEFAULT_CANONICAL_FILENAME
    history_filename: str = DEFAULT_HISTORY_FILENAME
    health_filename: str = DEFAULT_HEALTH_FILENAME
    divergence_filename: str = DEFAULT_DIVERGENCE_FILENAME
<<<<<<< HEAD
    cognition_filename: str = DEFAULT_COGNITION_FILENAME
    ai_recommendations_filename: str = DEFAULT_AI_RECOMMENDATIONS_FILENAME
    feedback_filename: str = DEFAULT_FEEDBACK_FILENAME
=======
    recommendations_state_filename: str = DEFAULT_RECOMMENDATIONS_STATE_FILENAME
>>>>>>> origin/main
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    cors_origins: list[str] = field(default_factory=list)
    cache_ttl_seconds: float = 0.5
    log_level: str = "INFO"

    @property
    def led_config_path(self) -> Path:
        return self.data_dir / self.led_config_filename

    @property
    def canonical_path(self) -> Path:
        return self.data_dir / self.canonical_state_filename

    @property
    def history_path(self) -> Path:
        return self.data_dir / self.history_filename

    @property
    def health_path(self) -> Path:
        return self.data_dir / self.health_filename

    @property
    def divergence_path(self) -> Path:
        return self.data_dir / self.divergence_filename

    @property
<<<<<<< HEAD
    def cognition_path(self) -> Path:
        return self.data_dir / self.cognition_filename

    @property
    def ai_recommendations_path(self) -> Path:
        return self.data_dir / self.ai_recommendations_filename

    @property
    def feedback_path(self) -> Path:
        return self.data_dir / self.feedback_filename
=======
    def recommendations_state_path(self) -> Path:
        return self.data_dir / self.recommendations_state_filename


class RecommendationUpdate(BaseModel):
    status: str
    details: Dict[str, Any] | None = None
>>>>>>> origin/main


class JsonFileCache:
    """Tiny cache around JSON files with TTL + mtime validation."""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = max(0.0, ttl_seconds)
        self._cache: Dict[Path, tuple[float, float, Any]] = {}

    def read(self, path: Path, allow_empty: bool = False) -> Optional[Any]:
        if not path.exists():
            return {} if allow_empty else None
        now = time.monotonic()
        cached = self._cache.get(path)
        mtime = path.stat().st_mtime
        if cached and now < cached[0] and cached[1] == mtime:
            return cached[2]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging.error("Invalid JSON in %s: %s", path, exc)
            return None
        expires = now + self._ttl if self._ttl else now
        self._cache[path] = (expires, mtime, data)
        return data


def create_app(config: ServiceConfig) -> FastAPI:
    cache = JsonFileCache(config.cache_ttl_seconds)
    app = FastAPI(title="Rehoboam API", version="1.0.0")

    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/status", summary="Current canonical LED state")
    def get_status() -> Dict[str, Any]:
        data = cache.read(config.canonical_path)
        if data is None:
            raise HTTPException(status_code=503, detail="Canonical state not available yet")
        return data

    @app.get("/config", summary="Current LED configuration")
    def get_config() -> Dict[str, Any]:
        data = cache.read(config.led_config_path)
        if data is None:
            raise HTTPException(status_code=503, detail="LED config not available yet")
        return data

    @app.get("/history", summary="Recent canonical state history")
    def get_history() -> Dict[str, Any]:
        data = cache.read(config.history_path, allow_empty=True)
        return data or {"entries": []}

    @app.get("/health", summary="Reported health of Jetson services")
    def get_health() -> Dict[str, Any]:
        data = cache.read(config.health_path, allow_empty=True)
        if not data:
            return {"status": "unknown", "services": []}
        return data

    @app.get("/info", summary="API metadata")
    def get_info() -> Dict[str, Any]:
        return {
            "app": app.title,
            "version": app.version,
            "files": {
                "canonical_state": str(config.canonical_path),
                "led_config": str(config.led_config_path),
                "history": str(config.history_path),
                "divergence": str(config.divergence_path),
                "cognition": str(config.cognition_path),
                "ai_recommendations": str(config.ai_recommendations_path),
                "feedback": str(config.feedback_path),
            },
        }

    @app.get("/divergence", summary="Latest divergence / anomaly score")
    def get_divergence() -> Dict[str, Any]:
        data = cache.read(config.divergence_path, allow_empty=True)
        if not data:
            raise HTTPException(status_code=404, detail="Divergence data not available")
        return data

    @app.get("/recommendations", summary="Actionable suggestions derived from ML service")
    def get_recommendations() -> Dict[str, Any]:
        data = cache.read(config.divergence_path, allow_empty=True)
        if not data:
            raise HTTPException(status_code=404, detail="Recommendations not available")
        recommendations = data.get("recommendations") or []
        return {
            "generated_at": data.get("generated_at"),
            "timestamp": data.get("timestamp"),
            "recommendations": recommendations,
        }

<<<<<<< HEAD
    @app.get("/cognition", summary="External orchestrator cognition feed (agents/decisions/approvals)")
    def get_cognition() -> Dict[str, Any]:
        data = cache.read(config.cognition_path, allow_empty=True)
        if not data:
            raise HTTPException(status_code=404, detail="Cognition not available")
        return data

    @app.get("/recommendations/ai", summary="AI-generated suggestions (for notifications/approvals)")
    def get_ai_recommendations() -> Dict[str, Any]:
        data = cache.read(config.ai_recommendations_path, allow_empty=True)
        if not data:
            raise HTTPException(status_code=404, detail="AI recommendations not available")
        return data

    @app.get("/feedback", summary="Approve/decline feedback events captured from Home Assistant")
    def get_feedback() -> Dict[str, Any]:
        data = cache.read(config.feedback_path, allow_empty=True)
        return data or {"feedback": []}

    @app.get("/recommendations/all", summary="Unified recommendations feed (ML + AI)")
    def get_all_recommendations() -> Dict[str, Any]:
        ml = cache.read(config.divergence_path, allow_empty=True) or {}
        ai = cache.read(config.ai_recommendations_path, allow_empty=True) or {}
        ml_recs = (ml.get("recommendations") or []) if isinstance(ml, dict) else []
        ai_recs = (ai.get("recommendations") or []) if isinstance(ai, dict) else []
        merged = []
        for rec in ml_recs:
            if isinstance(rec, dict):
                merged.append({**rec, "source": rec.get("source") or "ml"})
        for rec in ai_recs:
            if isinstance(rec, dict):
                merged.append({**rec, "source": rec.get("source") or "ai"})
        return {
            "generated_at": max(str(ml.get("generated_at") or ""), str(ai.get("generated_at") or "")),
            "timestamp": max(int(ml.get("timestamp") or 0), int(ai.get("timestamp") or 0)),
            "recommendations": merged,
        }
=======
    @app.post("/recommendations/{rec_id}", summary="Acknowledge/override a recommendation status")
    def set_recommendation_status(rec_id: str, update: RecommendationUpdate) -> Dict[str, Any]:
        normalized = (update.status or "").strip().lower()
        if normalized not in {"pending", "applied", "ignored"}:
            raise HTTPException(status_code=400, detail="status must be pending|applied|ignored")

        path = config.recommendations_state_path
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {}
        else:
            existing = {}
        if not isinstance(existing, dict):
            existing = {}
        existing.setdefault("schema_version", "1.0")
        items = existing.setdefault("items", {})
        if not isinstance(items, dict):
            items = {}
            existing["items"] = items

        entry = items.get(rec_id)
        if not isinstance(entry, dict):
            entry = {}
            items[rec_id] = entry
        entry["status"] = normalized
        entry["updated_at"] = time.time()
        if update.details:
            entry["details"] = update.details

        atomic_write_json(path, existing)
        return {"id": rec_id, "status": normalized}
>>>>>>> origin/main

    return app


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = overrides or RunnerOverrides()
    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    log_level = overrides.log_level or (data.get("logging", {}) or {}).get("level", "INFO")
    return ServiceConfig(
        data_dir=data_dir,
        led_config_filename=data.get("led_config_filename", DEFAULT_LED_CONFIG_FILENAME),
        canonical_state_filename=data.get("canonical_state_filename", DEFAULT_CANONICAL_FILENAME),
        history_filename=data.get("history_filename", DEFAULT_HISTORY_FILENAME),
        health_filename=data.get("health_filename", DEFAULT_HEALTH_FILENAME),
        host=data.get("host", "0.0.0.0"),
        port=int(data.get("port", 8000)),
        reload=bool(data.get("reload", False)),
        cors_origins=data.get("cors_origins", []),
        cache_ttl_seconds=float(data.get("cache_ttl_seconds", 0.5)),
        divergence_filename=data.get("divergence_filename", DEFAULT_DIVERGENCE_FILENAME),
<<<<<<< HEAD
        cognition_filename=data.get("cognition_filename", DEFAULT_COGNITION_FILENAME),
        ai_recommendations_filename=data.get("ai_recommendations_filename", DEFAULT_AI_RECOMMENDATIONS_FILENAME),
        feedback_filename=data.get("feedback_filename", DEFAULT_FEEDBACK_FILENAME),
=======
        recommendations_state_filename=data.get("recommendations_state_filename", DEFAULT_RECOMMENDATIONS_STATE_FILENAME),
>>>>>>> origin/main
        log_level=log_level,
    )


class _ApiServerWrapper:
    def __init__(self, config: ServiceConfig, host: str, port: int, reload_flag: bool, log_level: str) -> None:
        self._config = config
        self._host = host
        self._port = port
        self._server = uvicorn.Server(
            uvicorn.Config(
                create_app(config),
                host=host,
                port=port,
                reload=reload_flag,
                log_level=log_level.lower(),
            )
        )

    def run(self, run_once: bool = False) -> None:
        logging.info("Starting api_service on %s:%s", self._host, self._port)
        self._server.run()

    def request_stop(self, *_: Any) -> None:
        logging.info("Shutdown requested for api_service")
        self._server.should_exit = True


def main() -> None:
    def _add_extra_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--host", help="Override API host binding")
        parser.add_argument("--port", type=int, help="Override API port binding")
        parser.add_argument(
            "--reload",
            action="store_true",
            help="Enable FastAPI autoreload (dev only)",
        )

    def _create_service(config: ServiceConfig, args: argparse.Namespace) -> _ApiServerWrapper:
        host = args.host or config.host
        port = args.port or config.port
        reload_flag = args.reload or config.reload
        return _ApiServerWrapper(config, host, port, reload_flag, config.log_level)

    run_service(
        service_name="api_service",
        description="Serve canonical LED data via FastAPI",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
        add_arguments=_add_extra_args,
        supports_once=False,
        supports_interval_override=False,
    )


if __name__ == "__main__":
    main()
