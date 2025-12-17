#!/usr/bin/env python3
"""Ingest external orchestrator cognition + (optionally) generate AI recommendations."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

from jetson.common.config import expand_env_placeholders
from jetson.common.json_store import atomic_write_json, load_json
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service

DEFAULT_CONFIG_PATH = "jetson/cognition_service/config.yaml"

COGNITION_SCHEMA_VERSION = "1.0"
AI_RECOMMENDATIONS_SCHEMA_VERSION = "1.0"


@dataclass
class OrchestratorConfig:
    base_url: str
    timeout_seconds: float = 5.0
    verify_ssl: bool = True


@dataclass
class SuggestionsConfig:
    enabled: bool = False
    mode: str = "external_orchestrator_chat"
    chat_endpoint: str = "/api/chat"
    max_recommendations: int = 5
    cooldown_seconds: int = 900


@dataclass
class UserProfile:
    id: str
    name: str
    areas: List[str]


@dataclass
class ServiceConfig:
    data_dir: Path
    poll_interval_seconds: float
    orchestrator: OrchestratorConfig
    suggestions: SuggestionsConfig
    user_profiles: List[UserProfile]
    log_level: str = "INFO"

    @property
    def cognition_path(self) -> Path:
        return self.data_dir / "cognition.json"

    @property
    def ai_recommendations_path(self) -> Path:
        return self.data_dir / "ai_recommendations.json"

    @property
    def divergence_path(self) -> Path:
        return self.data_dir / "divergence.json"

    @property
    def raw_state_path(self) -> Path:
        return self.data_dir / "raw_state.json"

    @property
    def events_log_path(self) -> Path:
        return self.data_dir / "events.json"

    @property
    def sent_ledger_path(self) -> Path:
        return self.data_dir / "ai_recommendations_ledger.json"


class CognitionService:
    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._stop_requested = False
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="cognition_service")
        self._session = requests.Session()
        self._session.verify = config.orchestrator.verify_ssl
        self._ledger: Dict[str, Any] = load_json(config.sent_ledger_path, default={"last_sent": {}}) or {"last_sent": {}}

    def request_stop(self, *_: Any) -> None:
        logging.info("Stop requested; finishing current cycle")
        self._stop_requested = True

    def run(self, run_once: bool = False) -> None:
        self._health.mark_running(self._identity)
        while not self._stop_requested:
            started = time.monotonic()
            try:
                self.process_once()
                self._health.mark_running(self._identity)
            except Exception:
                logging.exception("cognition cycle failed")
                self._health.mark_error(self._identity, "cognition cycle failed")
            if run_once:
                break
            elapsed = time.monotonic() - started
            sleep_for = max(0.0, self._config.poll_interval_seconds - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

    def process_once(self) -> None:
        source = {"kind": "external_orchestrator", "base_url": self._config.orchestrator.base_url, "status": "ok"}
        agents: List[Dict[str, Any]] = []
        decisions: List[Dict[str, Any]] = []
        approvals: List[Dict[str, Any]] = []

        try:
            agents = self._get_json("/api/agents") or []
            decisions = self._get_json("/api/decisions?limit=50") or []
            # Keep status=pending by default; if the orchestrator ignores it, we still normalize.
            approvals = self._get_json("/api/approvals?status=pending") or []
        except Exception as exc:
            source["status"] = f"error: {exc}"
            logging.warning("Failed to fetch cognition from orchestrator: %s", exc)

        cognition_payload = {
            "schema_version": COGNITION_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": int(time.time()),
            "source": source,
            "agents": agents if isinstance(agents, list) else [],
            "decisions": decisions if isinstance(decisions, list) else [],
            "approvals": approvals if isinstance(approvals, list) else [],
        }
        atomic_write_json(self._config.cognition_path, cognition_payload)

        if not self._config.suggestions.enabled:
            return

        recommendations = self._generate_recommendations()
        payload = {
            "schema_version": AI_RECOMMENDATIONS_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": int(time.time()),
            "source": {
                "kind": "ai_recommendations",
                "engine": self._config.suggestions.mode,
                "base_url": self._config.orchestrator.base_url,
            },
            "recommendations": recommendations,
        }
        atomic_write_json(self._config.ai_recommendations_path, payload)

        # Persist local ledger (cooldowns / last suggestion timestamps).
        atomic_write_json(self._config.sent_ledger_path, self._ledger)

    def _get_json(self, path: str) -> Any:
        base = self._config.orchestrator.base_url.rstrip("/")
        url = f"{base}{path}"
        resp = self._session.get(url, timeout=self._config.orchestrator.timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Any:
        base = self._config.orchestrator.base_url.rstrip("/")
        url = f"{base}{path}"
        resp = self._session.post(url, json=payload, timeout=self._config.orchestrator.timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        mode = (self._config.suggestions.mode or "").strip().lower()
        if mode == "rules":
            return self._generate_recommendations_from_rules()
        return self._generate_recommendations_from_orchestrator_chat()

    def _generate_recommendations_from_rules(self) -> List[Dict[str, Any]]:
        """Fallback generator: promote existing ML recommendations into AI recommendations."""
        divergence = load_json(self._config.divergence_path, default={}) or {}
        recs = divergence.get("recommendations") or []
        now = int(time.time())
        out: List[Dict[str, Any]] = []
        for rec in recs[: self._config.suggestions.max_recommendations]:
            suggestion = str(rec.get("suggestion") or "").strip()
            if not suggestion:
                continue
            rec_id = self._stable_id("ml", suggestion, str(rec.get("target") or ""), str(rec.get("trigger") or ""))
            if self._is_on_cooldown(rec_id, now):
                continue
            out.append(
                {
                    "id": rec_id,
                    "timestamp": int(rec.get("timestamp") or now),
                    "trigger": rec.get("trigger"),
                    "target": rec.get("target"),
                    "suggestion": suggestion,
                    "confidence": rec.get("confidence", 0.5),
                    "status": rec.get("status", "pending"),
                    "target_users": [],
                }
            )
            self._mark_sent(rec_id, now)
        return out

    def _generate_recommendations_from_orchestrator_chat(self) -> List[Dict[str, Any]]:
        """Ask the external orchestrator for JSON-only, suggest-only recommendations."""
        context = {
            "raw_state": load_json(self._config.raw_state_path, default={}) or {},
            "divergence": load_json(self._config.divergence_path, default={}) or {},
            "events": (load_json(self._config.events_log_path, default={}) or {}).get("events", []),
            "users": [profile.__dict__ for profile in self._config.user_profiles],
        }
        # Keep prompt compact; this endpoint is not guaranteed to be stable across orchestrator versions.
        prompt = (
            "Generate up to {max_n} home-control suggestions as JSON only. "
            "Do NOT call or execute any Home Assistant services. "
            "Return ONLY a JSON object with this exact shape:\n"
            "{{\"recommendations\":[{{\"id\":\"...\",\"timestamp\":{now},\"suggestion\":\"...\",\"status\":\"pending\","
            "\"confidence\":0.0,\"trigger\":\"...\",\"area\":\"...\",\"target\":\"...\",\"target_users\":[\"...\"],"
            "\"actions\":[{{\"kind\":\"ha_service\",\"domain\":\"script\",\"service\":\"turn_on\",\"entity_id\":\"script.example\"}}],"
            "\"expires_at\":{expires}}}]}}\n"
            "Use stable ids and prefer calling scripts/scenes (not raw service calls) in actions.\n"
            "Context:\n"
        ).format(
            max_n=self._config.suggestions.max_recommendations,
            now=int(time.time()),
            expires=int(time.time()) + 900,
        )
        try:
            resp = self._post_json(self._config.suggestions.chat_endpoint, {"message": prompt + json.dumps(context)[:12000]})
        except Exception as exc:
            logging.warning("Suggestion chat request failed: %s", exc)
            return []

        text = self._extract_text(resp)
        parsed = self._extract_json(text)
        recommendations = (parsed or {}).get("recommendations") if isinstance(parsed, dict) else None
        if not isinstance(recommendations, list):
            return []

        now = int(time.time())
        out: List[Dict[str, Any]] = []
        for rec in recommendations[: self._config.suggestions.max_recommendations]:
            if not isinstance(rec, dict):
                continue
            suggestion = str(rec.get("suggestion") or "").strip()
            if not suggestion:
                continue
            rec_id = str(rec.get("id") or "").strip() or self._stable_id("ai", suggestion, str(rec.get("target") or ""), str(rec.get("trigger") or ""))
            if self._is_on_cooldown(rec_id, now):
                continue
            rec["id"] = rec_id
            rec["timestamp"] = int(rec.get("timestamp") or now)
            rec.setdefault("status", "pending")
            out.append(rec)
            self._mark_sent(rec_id, now)
        return out

    @staticmethod
    def _extract_text(resp: Any) -> str:
        if isinstance(resp, str):
            return resp
        if isinstance(resp, dict):
            for key in ("response", "message", "text", "content"):
                if isinstance(resp.get(key), str):
                    return resp[key]
            # Some APIs return nested objects (e.g., {"message":{"content":"..."}})
            nested = resp.get("message")
            if isinstance(nested, dict) and isinstance(nested.get("content"), str):
                return nested["content"]
        return json.dumps(resp)

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Best-effort: extract first JSON object substring.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def _stable_id(prefix: str, suggestion: str, target: str, trigger: str) -> str:
        base = f"{prefix}:{trigger}:{target}:{suggestion}".encode("utf-8")
        return f"{prefix}_{hashlib.sha1(base).hexdigest()[:12]}"

    def _is_on_cooldown(self, rec_id: str, now: int) -> bool:
        last_sent = (self._ledger.get("last_sent") or {}).get(rec_id)
        if not last_sent:
            return False
        try:
            last = int(last_sent)
        except (TypeError, ValueError):
            return False
        return (now - last) < self._config.suggestions.cooldown_seconds

    def _mark_sent(self, rec_id: str, now: int) -> None:
        self._ledger.setdefault("last_sent", {})[rec_id] = now


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data = expand_env_placeholders(data)
    overrides = overrides or RunnerOverrides()

    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    poll_interval = overrides.poll_interval_seconds or float(data.get("poll_interval_seconds", 10))
    log_level = overrides.log_level or (data.get("logging", {}) or {}).get("level", "INFO")

    orch = data.get("orchestrator") or {}
    orchestrator = OrchestratorConfig(
        base_url=str(orch.get("base_url") or "").strip(),
        timeout_seconds=float(orch.get("timeout_seconds", 5)),
        verify_ssl=bool(orch.get("verify_ssl", True)),
    )
    if not orchestrator.base_url:
        raise ValueError("orchestrator.base_url is required")

    sug = data.get("suggestions") or {}
    suggestions = SuggestionsConfig(
        enabled=bool(sug.get("enabled", False)),
        mode=str(sug.get("mode", "external_orchestrator_chat")),
        chat_endpoint=str(sug.get("chat_endpoint", "/api/chat")),
        max_recommendations=int(sug.get("max_recommendations", 5)),
        cooldown_seconds=int(sug.get("cooldown_seconds", 900)),
    )

    profiles: List[UserProfile] = []
    for raw in data.get("user_profiles") or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        profiles.append(
            UserProfile(
                id=str(raw.get("id")),
                name=str(raw.get("name") or raw.get("id")),
                areas=[str(a) for a in (raw.get("areas") or [])],
            )
        )

    return ServiceConfig(
        data_dir=data_dir,
        poll_interval_seconds=poll_interval,
        orchestrator=orchestrator,
        suggestions=suggestions,
        user_profiles=profiles,
        log_level=log_level,
    )


def main() -> None:
    def _create_service(config: ServiceConfig, _: argparse.Namespace) -> CognitionService:
        logging.info("cognition_service writing to %s", config.cognition_path)
        return CognitionService(config)

    run_service(
        service_name="cognition_service",
        description="Ingest external orchestrator cognition and generate AI recommendations",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
    )


if __name__ == "__main__":
    main()

