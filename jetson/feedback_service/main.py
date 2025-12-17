#!/usr/bin/env python3
"""Normalize HA actionable notification responses into feedback.json and update recommendation status."""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from jetson.common.config import expand_env_placeholders
from jetson.common.json_store import atomic_write_json, load_json
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service

DEFAULT_CONFIG_PATH = "jetson/feedback_service/config.yaml"
FEEDBACK_SCHEMA_VERSION = "1.0"


@dataclass
class ServiceConfig:
    data_dir: Path
    poll_interval_seconds: float
    max_entries: int
    log_level: str = "INFO"

    @property
    def events_log_path(self) -> Path:
        return self.data_dir / "events.json"

    @property
    def ai_recommendations_path(self) -> Path:
        return self.data_dir / "ai_recommendations.json"

    @property
    def feedback_path(self) -> Path:
        return self.data_dir / "feedback.json"


class FeedbackService:
    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._stop_requested = False
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="feedback_service")

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
                logging.exception("feedback cycle failed")
                self._health.mark_error(self._identity, "feedback cycle failed")
            if run_once:
                break
            elapsed = time.monotonic() - started
            sleep_for = max(0.0, self._config.poll_interval_seconds - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

    def process_once(self) -> None:
        events_payload = load_json(self._config.events_log_path, default={}) or {}
        events = events_payload.get("events") if isinstance(events_payload, dict) else None
        if not isinstance(events, list) or not events:
            return

        feedback_payload = load_json(self._config.feedback_path, default={"schema_version": FEEDBACK_SCHEMA_VERSION, "feedback": []}) or {
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "feedback": [],
        }
        existing = feedback_payload.get("feedback") or []
        if not isinstance(existing, list):
            existing = []
        existing_ids = {str(item.get("id")) for item in existing if isinstance(item, dict)}

        new_items: List[Dict[str, Any]] = []
        for event in events:
            item = self._event_to_feedback(event)
            if not item:
                continue
            if item["id"] in existing_ids:
                continue
            new_items.append(item)
            existing_ids.add(item["id"])

        if not new_items:
            return

        merged = (existing + new_items)[-self._config.max_entries :]
        out = {
            "schema_version": FEEDBACK_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": int(time.time()),
            "feedback": merged,
        }
        atomic_write_json(self._config.feedback_path, out)

        # Update AI recommendation statuses (best-effort).
        self._apply_feedback_to_ai_recommendations(new_items)

    def _apply_feedback_to_ai_recommendations(self, feedback_items: List[Dict[str, Any]]) -> None:
        payload = load_json(self._config.ai_recommendations_path, default=None)
        if not isinstance(payload, dict):
            return
        recs = payload.get("recommendations")
        if not isinstance(recs, list) or not recs:
            return

        # Map recommendation_id -> latest decision
        decisions: Dict[str, str] = {}
        for item in feedback_items:
            rec_id = str(item.get("recommendation_id") or "")
            decision = str(item.get("decision") or "")
            if rec_id and decision:
                decisions[rec_id] = decision

        if not decisions:
            return

        changed = False
        for rec in recs:
            if not isinstance(rec, dict):
                continue
            rec_id = str(rec.get("id") or "")
            if rec_id in decisions and str(rec.get("status") or "pending").lower() == "pending":
                rec["status"] = decisions[rec_id]
                changed = True

        if changed:
            payload["generated_at"] = datetime.now(timezone.utc).isoformat()
            payload["timestamp"] = int(time.time())
            atomic_write_json(self._config.ai_recommendations_path, payload)

    @staticmethod
    def _event_to_feedback(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(event, dict):
            return None
        if event.get("event_type") != "mobile_app_notification_action":
            return None
        action = str(event.get("action") or "")
        user_id = str(event.get("context_user_id") or "")
        device_id = str(event.get("device_id") or "")

        decision, rec_id = FeedbackService._parse_action(action)
        if not decision or not rec_id:
            return None

        ts = FeedbackService._event_epoch(event)
        fb_id = FeedbackService._stable_id(rec_id, decision, user_id, str(ts))
        return {
            "id": fb_id,
            "timestamp": ts,
            "recommendation_id": rec_id,
            "decision": decision,
            "user_id": user_id,
            "device_id": device_id,
            "source": "ha_mobile_app",
        }

    @staticmethod
    def _parse_action(action: str) -> Tuple[Optional[str], Optional[str]]:
        # Actions are generated by notification_service:
        #   REHOBOAM_APPROVE:<id>, REHOBOAM_DECLINE:<id>, REHOBOAM_SNOOZE:<id>
        if ":" not in action:
            return None, None
        prefix, rec_id = action.split(":", 1)
        rec_id = rec_id.strip()
        prefix = prefix.strip().upper()
        if not rec_id:
            return None, None
        if prefix == "REHOBOAM_APPROVE":
            return "approved", rec_id
        if prefix == "REHOBOAM_DECLINE":
            return "declined", rec_id
        if prefix == "REHOBOAM_SNOOZE":
            return "snoozed", rec_id
        return None, None

    @staticmethod
    def _event_epoch(event: Dict[str, Any]) -> int:
        # Prefer timestamp_epoch from collector, fallback to now.
        epoch = event.get("timestamp_epoch")
        try:
            if epoch is not None:
                return int(float(epoch))
        except (TypeError, ValueError):
            pass
        # Try ISO string timestamp if present.
        ts = event.get("timestamp")
        if isinstance(ts, str):
            try:
                return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
            except ValueError:
                pass
        return int(time.time())

    @staticmethod
    def _stable_id(rec_id: str, decision: str, user_id: str, ts: str) -> str:
        raw = f"{rec_id}:{decision}:{user_id}:{ts}".encode("utf-8")
        return f"fb_{hashlib.sha1(raw).hexdigest()[:12]}"


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data = expand_env_placeholders(data)
    overrides = overrides or RunnerOverrides()

    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    poll_interval = overrides.poll_interval_seconds or float(data.get("poll_interval_seconds", 5))
    log_level = overrides.log_level or (data.get("logging", {}) or {}).get("level", "INFO")

    return ServiceConfig(
        data_dir=data_dir,
        poll_interval_seconds=poll_interval,
        max_entries=int(data.get("max_entries", 500)),
        log_level=log_level,
    )


def main() -> None:
    def _create_service(config: ServiceConfig, _: argparse.Namespace) -> FeedbackService:
        logging.info("feedback_service writing to %s", config.feedback_path)
        return FeedbackService(config)

    run_service(
        service_name="feedback_service",
        description="Normalize HA actionable notification feedback for learning",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
    )


if __name__ == "__main__":
    main()

