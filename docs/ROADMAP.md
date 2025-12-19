# Rehoboam Roadmap

This document tracks the implementation status and future plans for the Rehoboam project.

## 🟢 Core Platform (Jetson & Services)

The core microservices architecture is largely implemented.

- [x] **Config Agent (`config_sync_service`)**: Syncs LED config from Home Assistant.
- [x] **Telemetry Agent (`collector_service`)**: Collects raw metrics (Ping, Pi-hole, HA Events).
- [x] **State Engine (`state_engine_service`)**: Computes canonical state (Health + Activity).
- [x] **LED Encoder (`led_encoder_service`)**: Encodes frames for Teensy.
- [x] **API Service (`api_service`)**: Exposes status via HTTP/FastAPI.
- [ ] **ML Service (`ml_service`)**:
    - [x] Basic implementation
    - [ ] Advanced anomaly detection (Divergence score)
- [ ] **Cognition Service**: (Planned)
- [ ] **Feedback Service**: (Planned)
- [ ] **Notification Service**: (Planned)

## 🟠 Firmware (Teensy)

- [x] Basic LED control
- [x] Protocol Controller (Serial JSON parsing)
- [x] State Machine Skeleton
- [ ] **Notification Enqueuing**: Implement logic in `state_machine.cpp` (Issue #27).
- [ ] **State Manager Host Script**: Implement YAML config parsing (Issue #28).

## 🔵 Generative E-Ink Visualizer

A parallel visualization system for the e-paper display. See `docs/generative_eink_next_steps.md` for details.

- [ ] **Phase 1: Channel Daemon** (Issue #38)
    - [ ] Connect to HA WebSocket
    - [ ] Emit normalized channel payloads
- [ ] **Phase 2: Renderer Integration** (Issue #39)
    - [ ] Update `GenerativeArtScene` to consume channel data
    - [ ] Implement partial refresh scheduling
- [ ] **Phase 3: Transport & Telemetry** (Issue #40)
    - [ ] MQTT Bridge / FastAPI Endpoint
    - [ ] Status Heartbeat
- [ ] **Phase 4: Ops & Tooling** (Issue #41)
    - [ ] Systemd units
    - [ ] Dashboard hooks
- [ ] **Phase 5: Visual Refinement**
    - [ ] Tuning and expanded glyph library

## 🟣 Future / Research

- [ ] **Cognition & Feedback**: Feedback loops for the system to "express" itself based on divergence.
- [ ] **Managed Switch Integration**: SNMP support in Telemetry Agent.
- [ ] **Advanced ML**: Local training on Jetson for behavioral baselines.

## 🛠️ Maintenance & Bug Fixes

- [x] **Ping Timeout**: Fix integer truncation in collector service (Issue #16).
- [x] **Firmware Compilation**: Add missing ArduinoJson headers (Issue #17).
- [x] **Type Annotations**: Fix return type in DivergenceScene (Issue #18).
- [x] **Tests**: Fix missing dependencies for root test runner (Issue #13).
- [x] **Documentation**: Update Roadmap (Issue #29).
