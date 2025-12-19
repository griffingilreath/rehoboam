# Protocol Specification

Centralized reference for host ↔ Teensy messaging.

## Command Frames
- `READY` – host indicates live data available; Teensy exits startup when current loop completes.
- `STATE:<LIVE|STANDBY>` – set the base operating state.
- `NOTIFY:<type>:<ttl_ms>` – transient notification pattern.
- `ALARM:<id>:<ON|OFF>` – critical alert activation/clear.
- `PING` – heartbeat to prevent error watchdog from engaging.
- `DATA:<payload>` – structured live data frame (payload schema TBD).
- `{"frame_id":..., "leds":...}` - JSON telemetry frame for live LED updates.

## Responses
- `ACK:<command>` – positive acknowledgement.
- `ERR:<reason>` – parsing or execution error.

Future iterations will promote these definitions into generated headers (`protocol_constants.hpp`) and Python modules (`protocol/constants.py`).
