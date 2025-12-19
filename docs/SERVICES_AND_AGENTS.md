# SERVICES_AND_AGENTS.md

This document describes each service/agent in detail so implementations can be generated consistently.

All Jetson services are expected to be:

- Written in **Python 3**.
- Runnable as `python main.py` (from the service directory or root).
- Configurable via:
  - A simple `config.yaml` or environment variables (defaults to `config.yaml` in the service directory).
  - Shared JSON files in a `data/` directory (or similar).
- Graceful if dependencies (HA, Pi-hole, serial device) are not yet available.

Directories are assumed to live under `jetson/` unless noted otherwise.

## Common Conventions

- **Data dir** (example): `./data/`
  - `led_config.json`
  - `raw_state.json`
  - `canonical_state.json`
- **Logging**: use `logging` module, log to stdout by default.
- **JSON**: use snake_case keys, UTF-8, no BOM.
- **Intervals**:
  - Telemetry collection: every 1–3 seconds.
  - State engine update: same or slightly offset.
  - LED frames: up to ~10 frames/second; can be lower if changes are infrequent.

---

## 1. Config Agent – `config_sync_service`

Path: `jetson/config_sync_service/main.py`

**Responsibility**

- Maintain a local `led_config.json` that describes:
  - What each LED (0–15) represents.
  - IP addresses and types (bridge, pihole, server, etc.).
  - Relevant HA availability entities.

**Inputs**

- Home Assistant helper entities, e.g.:
  - `input_text.led0_name`
  - `input_text.led0_ip`
  - `input_select.led0_type`
- Optionally: HA may also contain helper fields for HA availability entity names.

**Output**

`./data/led_config.json`:

---

## Cognition Bridge – `cognition_service`

Path: `jetson/cognition_service/main.py`

**Responsibility**

- **Option A**: ingest an external orchestrator’s agent/decision/approval feeds into `data/cognition.json`.
- **Option B**: generate structured, *suggest-only* recommendations into `data/ai_recommendations.json` (no execution).

**Outputs**

- `data/cognition.json`
- `data/ai_recommendations.json`

---

## Notifications – `notification_service`

Path: `jetson/notification_service/main.py`

**Responsibility**

- Send Home Assistant **actionable notifications** for `ai_recommendations.json` on a per-user basis.
- Maintain `notifications_sent.json` to avoid duplicates.

**Outputs**

- `data/notifications_sent.json`

---

## Feedback – `feedback_service`

Path: `jetson/feedback_service/main.py`

**Responsibility**

- Read `data/events.json` and extract `mobile_app_notification_action` events emitted by HA Companion apps.
- Normalize feedback into `data/feedback.json` and update AI recommendation statuses.

**Outputs**

- `data/feedback.json`
