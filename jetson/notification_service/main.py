#!/usr/bin/env python3
"""Send Home Assistant actionable notifications for AI recommendations."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import requests
import yaml

from jetson.common.config import expand_env_placeholders
from jetson.common.json_store import atomic_write_json, load_json
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service

DEFAULT_CONFIG_PATH = "jetson/notification_service/config.yaml"


@dataclass
class HomeAssistantConfig:
    base_url: str
    token: str
    timeout_seconds: float = 10.0
    verify_ssl: bool = True


@dataclass
class NotifyTarget:
    user_id: str
    notify_service: str
    title: str = "Rehoboam"


@dataclass
class ServiceConfig:
    data_dir: Path
    poll_interval_seconds: float
    home_assistant: HomeAssistantConfig
    notify_targets: List[NotifyTarget]
    default_user_ids: List[str]
    min_resend_seconds: int
    log_level: str = "INFO"

    @property
    def ai_recommendations_path(self) -> Path:
        return self.data_dir / "ai_recommendations.json"

    @property
    def sent_ledger_path(self) -> Path:
        return self.data_dir / "notifications_sent.json"


class HomeAssistantClient:
    def __init__(self, config: HomeAssistantConfig) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._timeout = config.timeout_seconds
        self._session = requests.Session()
        self._session.verify = config.verify_ssl
        self._session.headers.update({"Authorization": f"Bearer {config.token}", "Content-Type": "application/json"})

    def call_service(self, domain: str, service: str, payload: Dict[str, Any]) -> None:
        url = f"{self._base_url}/api/services/{domain}/{service}"
        resp = self._session.post(url, json=payload, timeout=self._timeout)
        resp.raise_for_status()


class NotificationService:
    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._ha = HomeAssistantClient(config.home_assistant)
        self._stop_requested = False
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="notification_service")
        self._targets = {t.user_id: t for t in config.notify_targets}
        self._ledger = load_json(config.sent_ledger_path, default={"sent": {}}) or {"sent": {}}

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
                logging.exception("notification cycle failed")
                self._health.mark_error(self._identity, "notification cycle failed")
            if run_once:
                break
            elapsed = time.monotonic() - started
            sleep_for = max(0.0, self._config.poll_interval_seconds - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

    def process_once(self) -> None:
        payload = load_json(self._config.ai_recommendations_path, default={}) or {}
        recs = payload.get("recommendations") or []
        if not isinstance(recs, list):
            return

        now = int(time.time())
        sent_map = self._ledger.setdefault("sent", {})

        for rec in recs:
            if not isinstance(rec, dict):
                continue
            rec_id = str(rec.get("id") or "").strip()
            if not rec_id:
                continue
            status = str(rec.get("status") or "pending").lower()
            if status != "pending":
                continue
            if self._recently_sent(sent_map, rec_id, now):
                continue

            target_users = rec.get("target_users")
            if isinstance(target_users, list) and target_users:
                user_ids = [str(u) for u in target_users if str(u)]
            else:
                user_ids = list(self._config.default_user_ids)

            if not user_ids:
                # Nothing configured; skip rather than spamming an unknown default.
                continue

            for user_id in user_ids:
                target = self._targets.get(user_id)
                if not target:
                    continue
                self._send_actionable_notification(target, rec)

            sent_map[rec_id] = {"last_sent": now, "tag": self._tag_for(rec_id), "users": user_ids}

        atomic_write_json(self._config.sent_ledger_path, self._ledger)

    def _send_actionable_notification(self, target: NotifyTarget, rec: Dict[str, Any]) -> None:
        rec_id = str(rec.get("id"))
        message = str(rec.get("suggestion") or "").strip()
        if not message:
            return

        # Action IDs must be <= 50 chars for some mobile clients; keep them compact.
        approve_action = f"REHOBOAM_APPROVE:{rec_id}"
        decline_action = f"REHOBOAM_DECLINE:{rec_id}"
        snooze_action = f"REHOBOAM_SNOOZE:{rec_id}"

        # notify_service is like "notify.mobile_app_x"
        domain, service = target.notify_service.split(".", 1) if "." in target.notify_service else ("notify", target.notify_service)
        if domain != "notify":
            # HA notify services always live under the "notify" domain.
            domain = "notify"

        payload = {
            "title": target.title,
            "message": message,
            "data": {
                "tag": self._tag_for(rec_id),
                "actions": [
                    {"action": approve_action, "title": "Approve"},
                    {"action": decline_action, "title": "Decline"},
                    {"action": snooze_action, "title": "Snooze"},
                ],
                "notification_icon": "mdi:robot",
            },
        }
        self._ha.call_service(domain, service, payload)
        logging.info("Sent actionable notification for %s to %s", rec_id, target.user_id)

    @staticmethod
    def _tag_for(rec_id: str) -> str:
        return f"rehoboam_rec_{rec_id}"

    def _recently_sent(self, sent_map: Dict[str, Any], rec_id: str, now: int) -> bool:
        entry = sent_map.get(rec_id) or {}
        last = entry.get("last_sent")
        try:
            last_i = int(last)
        except (TypeError, ValueError):
            return False
        return (now - last_i) < self._config.min_resend_seconds


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

    ha_raw = data.get("home_assistant") or {}
    ha = HomeAssistantConfig(
        base_url=str(ha_raw.get("base_url") or "").strip(),
        token=str(ha_raw.get("token") or "").strip(),
        timeout_seconds=float(ha_raw.get("timeout_seconds", 10)),
        verify_ssl=bool(ha_raw.get("verify_ssl", True)),
    )
    if not ha.base_url or not ha.token:
        raise ValueError("home_assistant.base_url and home_assistant.token are required")

    targets: List[NotifyTarget] = []
    for raw in data.get("notify_targets") or []:
        if not isinstance(raw, dict) or not raw.get("user_id") or not raw.get("notify_service"):
            continue
        targets.append(
            NotifyTarget(
                user_id=str(raw["user_id"]),
                notify_service=str(raw["notify_service"]),
                title=str(raw.get("title") or "Rehoboam"),
            )
        )

    default_user_ids = [str(u) for u in (data.get("default_user_ids") or [])]
    min_resend_seconds = int(data.get("min_resend_seconds", 3600))

    return ServiceConfig(
        data_dir=data_dir,
        poll_interval_seconds=poll_interval,
        home_assistant=ha,
        notify_targets=targets,
        default_user_ids=default_user_ids,
        min_resend_seconds=min_resend_seconds,
        log_level=log_level,
    )


def main() -> None:
    def _create_service(config: ServiceConfig, _: argparse.Namespace) -> NotificationService:
        logging.info("notification_service reading %s", config.ai_recommendations_path)
        return NotificationService(config)

    run_service(
        service_name="notification_service",
        description="Send Home Assistant actionable notifications for AI recommendations",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
    )


if __name__ == "__main__":
    main()

