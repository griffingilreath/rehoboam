# Teensy LED Status System Architecture

## System Overview
- **Goal**: Provide a resilient, glanceable LED status display for homelab and smart home events.
- **Components**: Teensy 4.x firmware running a prioritized state machine, host supervisor service (Pi/Jetson/Mac mini), USB serial link, and monitoring data sources (MQTT, REST, pings, sensors).
- **Design Pillars**: Non-blocking animations, deterministic state transitions, priority-based overrides, fault detection via heartbeats, modular configuration.

## State Machine
- **States**: `STARTUP`, `LIVE`, `STANDBY`, `NOTIFICATION`, `ALARM`, `ERROR`.
- **Priority Ladder**: `ALARM` > `ERROR` (communication loss) > `NOTIFICATION` > `LIVE`/`STANDBY` > `STARTUP` (auto-exits after completion).
- **Transitions**:
  - `STARTUP` → `LIVE` when host sends `READY` and current loop completes.
  - `LIVE` ↔ `STANDBY` driven by host `STATE` commands or inactivity timers.
  - `NOTIFICATION` flashes temporarily, then resumes previous base state.
  - `ALARM` holds until explicit `ALARM_CLEAR` command or manual reset.
  - `ERROR` activates when heartbeat timeout expires; clears on next valid message.
- **Implementation Sketch**:
  - `currentState` enum, `pendingState` queue for lower-priority requests.
  - `loop()` cycles: read serial → update timers → resolve highest priority state → step animation.
  - Each state exposes `enter()`, `step(uint32_t now)`, `exit()`.

## Animations
- **Structure**: Distinct classes/functions per animation under `firmware/src/animations` with configuration structs in `firmware/include/animations`.
- **Non-blocking**: Use `millis()` deltas and step indices; avoid `delay()`.
- **Customization Hooks**:
  - `startup` animation duration configurable via loops or milliseconds.
  - `standby` pattern accepts palette/brightness settings.
  - `live` mode can cycle submodes; host provides data frames.
  - `notification` and `alarm` share common flashing engine with intensity parameters.

## Communication Protocol
- **Physical Link**: USB serial (`115200` baud default).
- **Message Format**: Line-oriented ASCII frames: `COMMAND:ARG1:ARG2\n`.
- **Core Commands**:
  - `STATE:LIVE|STANDBY`
  - `READY`
  - `NOTIFY:<type>:<ttl_ms>`
  - `ALARM:<id>:ON|OFF`
  - `DATA:<json payload>` (compressed telemetry for live mode)
  - `PING`
- **Responses**: Teensy echoes `ACK:<command>` and periodic `HEARTBEAT:<timestamp>`.
- **Error Handling**: Invalid frames yield `ERR:<reason>`; host retries.

## Host Supervisor
- **Responsibilities**:
  - Monitor devices (ping, API, MQTT) and maintain priority queues for alarms/notifications.
  - Determine base state (live vs standby) based on environment context.
  - Stream live data frames when in `LIVE` state; send heartbeats every 30s.
  - Run as a `systemd` service or launch agent with auto-restart.
- **Structure** (`host/`):
  - `scripts/monitors/` individual check modules.
  - `scripts/protocol/` serial adapter, framing/parsing, retries.
  - `services/` supervisor orchestrator (e.g., `supervisor.py`).
  - `config/` YAML/JSON for device list, thresholds, serial settings.
- **Watchdog**: Tracks last `HEARTBEAT` from Teensy; reinitializes connection if stale.

## Shared Assets
- `shared/protocol/` contains protocol enums, message schema definitions, and host/firmware shared constants (exported as JSON or header files).

## Power & Safety
- Limit LED power draw via global brightness (e.g., 80/255) and optional FastLED power management.
- Common ground across Pi, Teensy, and LED strip.
- Optional Teensy hardware watchdog (5s window) to auto-reset hung firmware.

## Development Flow
1. Update firmware state logic in `firmware/src` with unit tests under `firmware/test` (e.g., using PlatformIO + Unity).
2. Adjust host supervisor modules and run integration tests under `host/tests`.
3. Sync protocol updates via shared schema files, regenerating constants for both sides.
4. Deploy: flash Teensy via PlatformIO task, restart host supervisor service.

## Future Extensions
- Add Web dashboard for override commands.
- Support MQTT bridge natively on Teensy Ethernet.
- Expand LED count with external 5V supply and power budget monitoring.
