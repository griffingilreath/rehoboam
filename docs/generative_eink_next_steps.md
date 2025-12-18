# Generative E-Ink Visualizer: Next Steps Plan

This document captures the concrete work packages required to bring the generative visualizer from research + scaffolding to a production-ready experience. Each milestone lists goals, deliverables, dependencies, and suggested owners so future pull requests remain cohesive.

## Phase 1 – Channel Daemon MVP

- **Goal:** Convert real Home Assistant events into semantic channel payloads.
- **Deliverables:**
  1. `visualizers/generative_eink/channel_daemon.py` (or equivalent) that:
     - Connects to the HA WebSocket API (`/api/websocket`)
     - Subscribes to `state_changed` events for entities defined in `entities.yaml`
     - Emits normalized features + channel dict at 1–5 Hz
     - Writes `data/generative_channels.json` and (optionally) publishes MQTT topic `rehoboam/viz/channels`
  2. Tests that replay recorded HA events (NDJSON fixture) and assert channel payloads match expectations.
- **Dependencies:** Finalize `entities.yaml` + `channels.yaml`; ensure Home Assistant has helper entities for every required feature.

## Phase 2 – Renderer Integration (epaper scene)

- **Goal:** Pull real channel payloads on the Pi and drive the IT8951 panel using the documented visual grammar.
- **Deliverables:**
  1. New `GenerativeScene` under `epaper/scenes/` that:
     - Reads channel payloads from `data/generative_channels.json` (file poll) or subscribes to MQTT
     - Reuses/render functions from `visualizers/generative_eink.examples.pi_weight_demo`
     - Implements partial refresh scheduling (per-region cadence, hourly GC16 refresh)
  2. Config updates so `epaper/config.yaml` can select `scene: generative`.
  3. Smoke test script `python -m epaper.cli.main --scene generative --backend fake` for CI.

## Phase 3 – Transport Hardening & Telemetry

- **Goal:** Make the channel feed resilient and observable.
- **Deliverables:**
  1. MQTT bridge (or lightweight FastAPI endpoint) with reconnection logic + exponential backoff.
  2. Status heartbeat `data/generative_renderer.json` capturing `{last_frame_ts, backend, mode}`.
  3. Integration into `service_health.json` (add entries for `visualizer_channel` and `visualizer_renderer`).

## Phase 4 – Ops & Tooling

- **Goal:** Ensure maintainable deployment on both Mac Mini (channel daemon) and Pi (renderer).
- **Deliverables:**
  1. Systemd units: `rehoboam-visualizer-channel.service` (Mac) & `rehoboam-visualizer-renderer.service` (Pi) mirroring shutdown semantics of existing agents.
  2. Dashboard hooks (devtools + iPhone) that display visualizer health + latest channel payloads for debugging.
  3. Documentation updates (`README.md`, `docs/it8951_driver_playbook.md`, `docs/generative_eink_visualizer_integration.md`) summarizing the new services and operational runbooks.

## Phase 5 – Visual Refinement

- **Goal:** Iterate on the art system itself using real household telemetry.
- **Deliverables:**
  1. Channel tuning sessions with recorded HA timelines (store NDJSON fixtures under `samples/ha_events/`).
  2. Expanded glyph library + region mapping documented in `docs/generative_eink_visualizer_research.md` (add image references / sketches as they become available).
  3. Optional experiments with multi-layer dithering, seasonal motifs, and event “cards” (JSON descriptors) for leaks, garage status, clean-energy windows, etc.

## Tracking & PR Guidance

- Treat each phase as its own pull request (or set of PRs) to keep reviews focused.
- Reference this plan plus `docs/generative_eink_visualizer_integration.md` in PR descriptions so reviewers can map work to milestones.
- Update the checklist below as work lands:

| Milestone | Status | PR/Issue |
|-----------|--------|----------|
| Channel daemon | ☐ | — |
| Generative scene | ☐ | — |
| Transport + telemetry | ☐ | — |
| Ops/systemd tooling | ☐ | — |
| Visual refinements | ☐ | — |

Feel free to clone this checklist into GitHub issues or the project board so each step is traceable.
