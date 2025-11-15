You don’t *have* to split it, but giving Cursor a couple of focused docs makes it way easier for it to “think like the system” instead of just like a pile of scripts.

What I’d recommend:

1. **`ARCHITECTURE.md`** – high-level overview, hardware, data flows, protocols, big picture.
2. **`SERVICES_AND_AGENTS.md`** – very concrete spec for each service/agent (what it does, inputs/outputs, file formats, CLI expectations, etc.).

You can drop both into the repo root so Cursor always sees them as context.

Below are both docs, already written so you can paste them straight into files.

---

````markdown
# ARCHITECTURE.md

## 1. Overview

This project uses a **Jetson Nano** to drive a **16-LED Neopixel status panel** (via a **Teensy microcontroller**) plus an optional **front display** (iPhone 12 Pro Max behind a 2-way mirror or an e-ink panel).

The system visualizes:

- **Health** of key devices/services:
  - Smart-home bridges (Hue, Lutron, Ikea Dirigera, Aqara, Eufy, Starling).
  - Network infrastructure (router/gateway, Pi-hole, Home Assistant, Mac mini, etc.).
- **Activity**:
  - Lighting & blind actions (Hue, Ikea, Lutron, Aqara, etc.).
  - DNS/Ad-blocking traffic from Pi-hole.
- **Future**: Anomaly / “divergence” score (inspired by Westworld’s Rehoboam) derived from normal vs. unusual behavior.

### Key constraints

- Switches are currently **unmanaged** (no SNMP/VLANs/port stats).
- Static or DHCP-reserved IPs will be assigned to critical devices.
- **Home Assistant** + **MQTT broker** already exist on the network.
- **Pi-hole** is accessible via HTTP API and optionally logs.
- Jetson runs **Linux**, and most services are written in **Python 3**.
- Teensy runs **Arduino C++** and drives a chain of **16 Neopixels**.
- Front display (if used) should consume JavaScript-friendly APIs (REST/WebSocket) from Jetson.

The design is intentionally modular and “agent-based” so services can restart independently, be containerized later, and evolve (e.g. more ML, managed switches with SNMP).


## 2. Hardware & Network

### 2.1 Devices

- **Jetson Nano**
  - Linux OS (Ubuntu-like).
  - Ethernet to LAN.
  - USB connection to Teensy.

- **Teensy (e.g., Teensy 3.2)**
  - Connected via USB to Jetson.
  - Appears as serial device (`/dev/ttyACM0` or similar).
  - Drives a single Neopixel chain of **16 LEDs** (indices 0–15).

- **LED Panel**
  - 16 discrete Neopixel LEDs embedded in a front panel.
  - One LED per “logical thing” (bridge/service/port/etc.).
  - The physical mapping is *configurable* rather than hard-coded.

- **Network Devices**
  - Router/gateway + Wi-Fi (Eero now, possibly UniFi later).
  - Unmanaged switches (core and/or remote).
  - Smart-home hubs:
    - Hue Bridge
    - Lutron Caséta Pro Bridge
    - Ikea Dirigera
    - Aqara M2
    - Eufy Security Hub
    - Starling Home Hub
  - **Pi-hole** (one or more instances).
  - **Home Assistant Green**.
  - **Mac mini**, Airport, and other hosts.

- **Front Display Options**
  - iPhone 12 Pro Max behind a two-way mirror in kiosk mode (Safari + Guided Access).
  - E-ink panel driven by Jetson or a small Pi (SPI or USB).


### 2.2 Network assumptions

- The router provides DHCP.
- Critical devices (Hue, Lutron, HA, Pi-hole, Jetson, Mac mini, etc.) have **static or DHCP-reserved IPs**.
- Unmanaged switches are fine — we do not depend on switch telemetry; we inspect device health via IP, Home Assistant, and APIs.
- If a managed switch is used in the future, SNMP integration can be added without redesigning the architecture.

---

## 3. Functional Overview

At a high level:

1. **Home Assistant** holds editable configuration for what each LED represents.
2. The **Jetson** synchronizes that configuration and collects raw telemetry:
   - Pings devices.
   - Polls Pi-hole API.
   - Listens to Home Assistant events (lights, blinds, automations).
3. A **state engine** on Jetson turns raw telemetry into a per-LED “canonical state”:
   - `health_status`: is it working?
   - `activity_level`: how busy recently?
   - `activity_type`: what kind of activity?
4. A **LED encoder** converts canonical state into compact frames and streams them to the **Teensy over serial**.
5. The **Teensy** applies animation rules and drives the Neopixels.
6. An **API service** on Jetson exposes the canonical state and history to front-end clients:
   - iPhone dashboard.
   - E-ink rendering script.
7. A future **ML service** can analyze history and compute anomaly / divergence scores.

---

## 4. Home Assistant as Config + Event Hub

### 4.1 LED mapping configuration in HA

We do **not** hard-code “LED 0 = Hue” in the firmware or Python code.

Instead, Home Assistant provides helpers such as:

- `input_text.led0_name`  – “Hue Bridge”
- `input_text.led0_ip`    – “192.168.1.10”
- `input_select.led0_type` – one of:
  - `bridge`, `pihole`, `server`, `router`, `ap`, `other`, etc.

This repeats for LED indices `0..15`.

A dedicated **“Rack Config” dashboard** in HA exposes these helpers for editing, so when devices move ports or IPs, the user only edits HA, not code.

The Jetson’s **Config Agent** reads these (via HA REST or via an MQTT automation) and writes a local `led_config.json`, which becomes the **source of truth** for all other Jetson services.

### 4.2 HA availability & event stream

Home Assistant also provides:

- **Availability entities** for bridges and key systems, e.g.:

  - `binary_sensor.hue_bridge_available`
  - `binary_sensor.lutron_bridge_available`
  - etc.

- **Event stream / state changes** via MQTT or WebSocket, e.g.:

  - `light.*` state changes (Hue, Ikea, Lutron, Aqara lights).
  - `cover.*` (blinds open/close).
  - `switch.*`, scenes, automations.

These are used to detect **activity** (lights toggling, blinds moving, automations firing) and to supplement health checks (e.g., a bridge that hasn’t reported in a while may be “ERROR” even if it pings).

---

## 5. Status Model: Health + Activity

Each LED has a logical “entity” behind it with two main concerns:

1. **Health** — binary/graded: is this thing OK?
2. **Activity** — how much stuff is happening *right now*?

### 5.1 Health status

Possible values:

- `OK`
- `WARNING`
- `ERROR`
- `OFFLINE` (intentionally off/disabled)
- `UNKNOWN` (no data yet)

Inputs for health:

- **Reachability**:
  - Ping responses to device IP.
  - Optional HTTP health check (where available).
- **Home Assistant availability**:
  - Specific binary sensors per bridge/service.
- **Pi-hole status**:
  - Pi-hole API reachable.
  - DNS test via Pi-hole.
- **Other contextual signals**:
  - Repeated timeouts.
  - Excessive latency.

Health maps to **base LED color**:

- `OK` → green.
- `WARNING` → amber.
- `ERROR` → red.
- `OFFLINE` → dim blue/off.
- `UNKNOWN` → neutral white/purple.

Health color is **primary**; activity never overrides the underlying hue, only animates it.

### 5.2 Activity

Activity represents **recent events** (seconds to tens of seconds), such as:

- Hue lights turning on/off.
- Ikea blinds moving.
- Lutron scenes changing.
- Pi-hole DNS queries and blocks.

Each LED has:

- `activity_level` (float 0.0–1.0)
- `activity_type` (string or small enum), e.g.:
  - `light_change`
  - `blind_move`
  - `dns_queries`
  - `blocked_query`
  - `generic_event`
  - `none`

Mechanics:

- Events from HA (light/cover/switch changes) or Pi-hole traffic **increment** `activity_level` for the corresponding LED (e.g., `+0.3` per event).
- `activity_level` decays over time (e.g., exponential decay each second).
- Pi-hole uses traffic rate (QPS) and block ratio to drive `activity_level` and `activity_type`.

Activity influences **animation**, not base hue:

- Low/zero activity → mostly solid LED.
- Moderate activity → gentle pulse.
- High activity → fast pulse / flicker.

Pi-hole specific design:

- **Pulse speed/brightness proportional to QPS.**
- **Color tint** can lean more red as the fraction of blocked queries increases.
- This approximates “flash per decision” without literally toggling for every single query.

---

## 6. Jetson Services & Data Flow

The Jetson runs multiple small services (“agents”), each with a single responsibility. They communicate via JSON files and/or in-process calls. (Later, this can be moved to Redis, message queues, etc., if needed.)

### 6.1 Config Agent (`config_sync_service`)

- Pulls LED config from Home Assistant, either:
  - via REST calls to HA’s state API, or
  - via MQTT topic `rack/ports/config` pushed by an HA automation.
- Produces `led_config.json`:

  ```json
  {
    "leds": [
      {
        "index": 0,
        "name": "Hue Bridge",
        "ip": "192.168.1.10",
        "type": "bridge",
        "ha_availability_entity": "binary_sensor.hue_bridge_available"
      }
      // ...
    ]
  }
````

* Other services reload this on startup and when changed.

### 6.2 Telemetry Agent (`collector_service`)

Collects **raw** metrics:

* For each entry in `led_config.json`:

  * **Ping** the IP (if present) to measure reachability and latency.
  * For `type = "pihole"`:

    * Call Pi-hole API for status, QPS, block rates.
    * Optionally tail Pi-hole logs (if accessible) for fine-grained counts.

* **Home Assistant events**:

  * Subscribes to HA events via MQTT or WebSocket.
  * Normalizes events like light toggles, cover moves, etc., tagged by device name or entity.

Outputs a `raw_state.json`:

```json
{
  "timestamp": 1731612345,
  "devices": {
    "Hue Bridge": {
      "reachable": true,
      "rtt_ms": 12,
      "ha_available": true,
      "events_last_5s": 3
    },
    "Pi-hole-1": {
      "api_ok": true,
      "dns_test_ok": true,
      "qps": 37,
      "blocked_ratio": 0.22
    }
  },
  "events": [
    {
      "timestamp": 1731612340,
      "source": "HomeAssistant",
      "kind": "light_change",
      "device": "Hue Bridge"
    },
    {
      "timestamp": 1731612341,
      "source": "PiHole",
      "kind": "dns_query",
      "blocked": true
    }
  ]
}
```

### 6.3 State Engine Agent (`state_engine_service`)

Consuming `raw_state.json` and `led_config.json`, this service:

* Converts reachability and availability into `health_status`.
* Maintains per-LED `activity_level` using event counts and decay.
* Assigns `activity_type` based on most recent/most significant events.
* Outputs a **canonical state** file `canonical_state.json`:

```json
{
  "timestamp": 1731612346,
  "leds": [
    {
      "index": 0,
      "name": "Hue Bridge",
      "health": "OK",
      "activity_level": 0.6,
      "activity_type": "light_change"
    },
    {
      "index": 1,
      "name": "Lutron",
      "health": "ERROR",
      "activity_level": 0.0,
      "activity_type": null
    },
    {
      "index": 2,
      "name": "Pi-hole-1",
      "health": "OK",
      "activity_level": 0.9,
      "activity_type": "dns_queries"
    }
  ]
}
```

`canonical_state.json` is the **single source of truth** for:

* LED behavior.
* Front displays (iPhone/e-ink).
* Future ML/anomaly logic.

### 6.4 LED Encoder Agent (`led_encoder_service`)

Reads `canonical_state.json` and converts it into compact frames for the Teensy over serial.

A frame example (JSON form):

```json
{
  "frame_id": 12345,
  "timestamp": 1731612346,
  "leds": [
    {"i": 0, "h": 0, "a": 0.6, "t": 1},
    {"i": 1, "h": 2, "a": 0.0, "t": 0},
    {"i": 2, "h": 0, "a": 0.9, "t": 2}
  ]
}
```

Where:

* `i` = LED index (0–15).
* `h` = health code (int):

  * 0 = OK
  * 1 = WARNING
  * 2 = ERROR
  * 3 = OFFLINE
  * 4 = UNKNOWN
* `a` = activity level (float 0–1).
* `t` = activity type code (int):

  * 0 = none
  * 1 = bridge_activity / light_change
  * 2 = pihole_traffic
  * 3 = blind_move
  * 4 = generic_event

Frames can be sent at a low but steady rate (e.g. 5–10 fps) or only on changes. The Teensy handles animation interpolation locally.

### 6.5 API Agent (`api_service`)

Exposes machine- and human-readable status for other clients:

* `GET /status` → `canonical_state.json`.
* `GET /config` → `led_config.json`.
* `GET /history` → last N seconds/minutes/hours of canonical states.
* `GET /divergence` (future) → anomaly score.

Used by:

* iPhone front dashboard (web page).
* E-ink rendering script.
* Debugging / observability tools.

### 6.6 ML / Analytics Agent (`ml_service`) – future

Not required initially; later it can:

* Subscribe to canonical state updates and/or read from a historical store (SQLite, InfluxDB, etc.).
* Learn normal patterns across time of day and day of week.
* Compute a “divergence score” for current behavior vs. baseline.
* Write divergence info back into:

  * `canonical_state.json` (extra field), or
  * A dedicated endpoint in `api_service`.

This divergence can be visualized on the front display and/or on a dedicated LED.

---

## 7. Teensy Firmware Responsibilities

The Teensy is responsible for **real-time animation** and **failsafe behavior**, not business logic.

Key responsibilities:

1. **Serial Input**

   * Read JSON frames from serial.
   * Parse with ArduinoJson or simple custom parser.
   * Update `led_state[16]`, each containing:

     * `health_code` (0–4).
     * `activity_level` (0–1).
     * `activity_type` (0–n).
   * Maintain `last_frame_millis`.

2. **Animation Loop**

   * Run at ~60 FPS (e.g. `delay(16)`).
   * For each LED:

     * Convert `health_code` to base RGB color.
     * Adjust brightness/pulse speed based on `activity_level`.
     * Apply pattern hints from `activity_type`:

       * `bridge_activity`: quick cyan pulse overlay.
       * `pihole_traffic`: flicker/pulse proportional to traffic intensity.
       * `blind_move`: vertical “wipe” style animation if desired.
   * Write resulting colors to Neopixels using FastLED or Adafruit_NeoPixel.

3. **Failsafe**

   * If no new frame is received for X ms (e.g. 5000 ms):

     * Enter a fallback pattern, e.g. gentle white breathing on all LEDs, to signal the Jetson/serial is down.

4. **Debugging**

   * Optionally blink the built-in Teensy LED on each received frame.
   * Optionally provide a simple serial command mode for testing patterns without Jetson.

---

## 8. Front Display Clients

Both front display options consume the same backend: `api_service`.

### 8.1 iPhone 12 Pro Max behind 2-way mirror

* iPhone runs Safari in full-screen mode (via Guided Access), pointed at e.g. `http://jetson-rack.local/dashboard`.
* The dashboard is a simple web app:

  * Calls `/status` (and optionally `/history` and `/divergence`) via REST or WebSocket.
  * Renders:

    * A grid or Rehoboam-style visualization of current services and health.
    * Pi-hole traffic mini-graphs.
    * A divergence visual over time (future).
  * Uses consistent color vocabulary with the LED panel (green/amber/red/etc.).

### 8.2 E-ink display

* A Python script (in `display_clients/eink_client`) does:

  * Every 30–60 seconds:

    * GET `/status`, `/history`, `/divergence`.
    * Render a grayscale image (using Pillow or similar).
    * Push this image to the e-ink display over SPI/I2C/USB.
* Because of slow refresh, it focuses on:

  * Trends and divergence.
  * Current high-level states, not every transient event.

---

## 9. Unmanaged Switch Considerations

Unmanaged switches provide no direct telemetry. The design therefore:

* **Does not depend on SNMP or port-level stats**.
* Infers health/activity via:

  * Device reachability (ping).
  * HA availability.
  * Service logs/APIs (Pi-hole, etc.).

When a managed switch is introduced later, the Telemetry Agent can be extended to:

* Query SNMP for port status, errors, and traffic.
* Tag LEDs with extra information (bandwidth, error counts).
* This will not require changes to the canonical data model or Teensy protocol.

---

## 10. Future: Anomaly / “Rehoboam” Visualization

Future extensions are explicitly enabled by this architecture:

* **Logging**: Canonical state can be appended to a time-series DB.
* **Anomaly detection**:

  * Compute a divergence score (0–1 or 0–100) based on deviation from normal patterns.
* **Visualization**:

  * Front display shows a Rehoboam-style cluster diagram where:

    * Nodes are devices/services.
    * Node radius/color/glow intensity represent divergence.
  * LED panel could dedicate one LED (or a pattern on all LEDs) to reflect global divergence levels.

These features bolt onto the existing canonical state without changing the LED protocol or base services.

````

---

Now a companion doc that’s more “this is exactly what each agent should do” for Cursor:

```markdown
# SERVICES_AND_AGENTS.md

This document describes each service/agent in detail so implementations can be generated consistently.

All Jetson services are expected to be:

- Written in **Python 3**.
- Runnable as `python main.py`.
- Configurable via:
  - A simple `config.yaml` or environment variables, and
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

```json
{
  "leds": [
    {
      "index": 0,
      "name": "Hue Bridge",
      "ip": "192.168.1.10",
      "type": "bridge",
      "ha_availability_entity": "binary_sensor.hue_bridge_available"
    },
    {
      "index": 1,
      "name": "Lutron",
      "ip": "192.168.1.11",
      "type": "bridge",
      "ha_availability_entity": "binary_sensor.lutron_bridge_available"
    }
  ]
}
````

**Behavior**

* On startup:

  * Fetch states for all `input_text.led*_name`, `input_text.led*_ip`, `input_select.led*_type`.
  * Build `led_config.json`.
* Periodically (e.g. every 30–60 seconds) or on demand:

  * Re-fetch and update `led_config.json` if changes are detected.
* Should handle missing helpers gracefully:

  * If a LED lacks config, either:

    * Omit it from `led_config.json`, or
    * Include with `type: "unknown"` and no IP.

---

## 2. Telemetry Agent – `collector_service`

Path: `jetson/collector_service/main.py`

**Responsibility**

* Collect raw metrics for each configured LED device:

  * Reachability (ping).
  * Pi-hole status and traffic.
  * HA availability.
* Listen to Home Assistant events to track activity.

**Inputs**

* `./data/led_config.json`
* Home Assistant:

  * REST/WS for availability, or HA entity states (optional).
  * MQTT/WS for events.
* Pi-hole:

  * HTTP API.
  * Optionally log file (if accessible).
* Network:

  * ICMP ping (or TCP connect time as fallback).

**Output**

`./data/raw_state.json`:

```json
{
  "timestamp": 1731612345,
  "devices": {
    "Hue Bridge": {
      "reachable": true,
      "rtt_ms": 12,
      "ha_available": true,
      "events_last_5s": 3
    },
    "Pi-hole-1": {
      "api_ok": true,
      "dns_test_ok": true,
      "qps": 37,
      "blocked_ratio": 0.22
    }
  },
  "events": [
    {
      "timestamp": 1731612340,
      "source": "HomeAssistant",
      "kind": "light_change",
      "device": "Hue Bridge"
    },
    {
      "timestamp": 1731612341,
      "source": "PiHole",
      "kind": "dns_query",
      "blocked": true
    }
  ]
}
```

**Behavior**

* On startup:

  * Load `led_config.json`.
  * Connect to HA (MQTT/WS) for events.
* Every N seconds (e.g. 1–3 seconds):

  * For each configured LED/device:

    * Ping its IP if present.
    * If `type == "pihole"`:

      * Call Pi-hole API for status, QPS, blocked ratio.
    * Optionally test DNS lookup via Pi-hole for a known domain (e.g. `example.com`).
  * Aggregate events from HA and Pi-hole into a recent time window (e.g. last 5 seconds).
  * Write `raw_state.json`.

Should be robust against:

* Missing `led_config.json` (wait until it appears).
* Unreachable HA or Pi-hole (log errors, mark those fields accordingly).

---

## 3. State Engine Agent – `state_engine_service`

Path: `jetson/state_engine_service/main.py`

**Responsibility**

* Convert `raw_state.json` + `led_config.json` into a **canonical per-LED state** with `health`, `activity_level`, and `activity_type`.

**Inputs**

* `./data/led_config.json`
* `./data/raw_state.json`

**Output**

`./data/canonical_state.json`:

```json
{
  "timestamp": 1731612346,
  "leds": [
    {
      "index": 0,
      "name": "Hue Bridge",
      "health": "OK",
      "activity_level": 0.6,
      "activity_type": "light_change"
    },
    {
      "index": 1,
      "name": "Lutron",
      "health": "ERROR",
      "activity_level": 0.0,
      "activity_type": null
    }
  ]
}
```

**Behavior**

* Maintain in-memory state for each LED:

  * Last health state.
  * `activity_level` (float 0–1).
  * `activity_type` (enum or string).
* On each tick (e.g. 1–3 sec):

  * Read `raw_state.json`.
  * For each LED/device:

    * Determine `health` by rules:

      * `OK`: reachable + healthy responses.
      * `WARNING`: reachable but high latency or intermittent issues.
      * `ERROR`: unreachable or failed health checks.
      * `OFFLINE`: intentionally disabled (e.g. Pi-hole status disabled).
      * `UNKNOWN`: insufficient data.
    * Update `activity_level`:

      * Add contributions based on recent events count.
      * Apply exponential or linear decay.
    * Update `activity_type`:

      * Most recent significant event type (light changes, blind moves, DNS).
  * Write the canonical JSON.

Rules should be centralized in `rules.py` so they can be adjusted without changing main logic.

---

## 4. LED Encoder Agent – `led_encoder_service`

Path: `jetson/led_encoder_service/main.py`

**Responsibility**

* Translate canonical LED state into a compact frame for the Teensy and send via serial.

**Inputs**

* `./data/canonical_state.json`
* Serial device path (e.g. `/dev/ttyACM0`).

**Output**

* Serial writes of JSON frames to Teensy.

**Frame Format**

Example:

```json
{
  "frame_id": 12345,
  "timestamp": 1731612346,
  "leds": [
    {"i": 0, "h": 0, "a": 0.6, "t": 1},
    {"i": 1, "h": 2, "a": 0.0, "t": 0},
    {"i": 2, "h": 0, "a": 0.9, "t": 2}
  ]
}
```

Where:

* `i`: LED index (0–15).
* `h`: health code:

  * 0 = OK
  * 1 = WARNING
  * 2 = ERROR
  * 3 = OFFLINE
  * 4 = UNKNOWN
* `a`: activity level (0.0–1.0).
* `t`: activity type code:

  * 0 = none
  * 1 = bridge_activity/light_change
  * 2 = pihole_traffic
  * 3 = blind_move
  * 4 = generic_event

**Behavior**

* On startup:

  * Open serial port.
* Loop (e.g. every 100–200 ms):

  * Read `canonical_state.json`.
  * Build the frame structure.
  * Serialize to JSON.
  * Write to serial.
* Handle serial write failures gracefully (log, retry).

Can include a mode that only sends when `canonical_state.json` changes (based on timestamp/hash) to reduce noise.

---

## 5. API Agent – `api_service`

Path: `jetson/api_service/main.py`

**Responsibility**

* Serve canonical state and related info via HTTP for dashboards and tools.

**Framework**

* Recommended: **FastAPI** (or Flask if simpler).

**Endpoints**

* `GET /status`

  * Returns `canonical_state.json` structure.
* `GET /config`

  * Returns `led_config.json`.
* `GET /history`

  * Returns recent history of canonical states (implementation-specific; could be an in-memory buffer or separate log file/DB).
* `GET /health`

  * Returns basic health info of Jetson services.
* `GET /divergence` (future)

  * Returns a numeric anomaly score for the system.

**Behavior**

* On startup:

  * Load latest `canonical_state.json` and `led_config.json`.
* On request:

  * Read files fresh or maintain a background watcher to serve up-to-date data.
* Optionally:

  * Provide a WebSocket endpoint that pushes updated canonical state to clients (for smoother dashboards).

---

## 6. ML / Analytics Agent – `ml_service` (Future)

Path: `jetson/ml_service/main.py`

**Responsibility**

* Analyze historical canonical states to compute an anomaly/divergence score.

**Inputs**

* Canonical state stream (via polling `canonical_state.json` or reading from an append-only log/DB).
* Time-series database or log file (depending on implementation).

**Output**

* `divergence_score` (0–1 or 0–100).
* Optionally:

  * A `divergence` field appended to `canonical_state.json`.
  * An endpoint in `api_service` for `/divergence`.

**Behavior**

* Initial simple implementation:

  * Statistical baseline (mean/sd per hour of day) for chosen metrics (QPS, number of unavailable devices, activity levels).
  * Score current state based on z-scores.
* Future:

  * More advanced time-series models or small ML models running locally on Jetson.

---

## 7. Teensy Firmware Agent

Path: `teensy/led_controller/led_controller.ino`

**Responsibility**

* Receive LED frames from Jetson.
* Animate and display health + activity on Neopixels.
* Provide a failsafe pattern when no frames arrive.

**Inputs**

* Serial data frames as specified above.

**Behavior**

* Setup:

  * Initialize serial.
  * Initialize Neopixel strip with 16 LEDs.
* Loop:

  * Check for available serial data.

    * Read bytes.
    * Parse JSON frame (ArduinoJson).
    * Update `led_state[16]` with health, activity, type, and update `last_frame_millis`.
  * For each LED:

    * Compute base color based on health code.
    * Apply brightness/pulse based on `activity_level`.
    * Optional pattern variations based on `activity_type`.
  * If `millis() - last_frame_millis` > timeout:

    * Run fallback pattern (e.g. slow breathing white).
  * Show Neopixel state (`FastLED.show()` or equivalent).
  * Delay to maintain ~50–60 FPS.

---

## 8. Display Clients

### 8.1 iPhone Dashboard

Path: `display_clients/iphone_dashboard/`

Files:

* `index.html`
* `app.js`
* `styles.css`

**Responsibility**

* Render a live dashboard  in Safari on the iPhone, using `/status` (and optionally `/history`, `/divergence`).

**Behavior**

* On load:

  * Fetch `/status` and render initial state.
  * Optionally open a WebSocket for live updates.
* Display:

  * Grid or diagram of services with color-coded health status.
  * Simple visuals of Pi-hole activity, network health, etc.
  * Optional Rehoboam-style layout for divergence visualization.

### 8.2 E-ink Client

Path: `display_clients/eink_client/render.py`

**Responsibility**

* Periodically render a static summary image for an e-ink display.

**Behavior**

* Every 30–60 seconds:

  * GET `/status` and `/history`.
  * Use Pillow (or similar) to generate a PNG or bitmap.
  * Send to the e-ink panel via appropriate driver (implementation detail).
* Focus on:

  * High-level overview of which services are OK/warning/error.
  * Pi-hole trend graph.
  * Global divergence indicator (future).

---

## 9. Implementation Order (Suggested)

1. Implement `config_sync_service` (with mock HA).
2. Implement `collector_service` (with simple pings and mocked Pi-hole/HA).
3. Implement `state_engine_service` (rules + canonical state).
4. Implement `led_encoder_service` with a dummy serial sink.
5. Implement Teensy firmware to parse frames and animate a test pattern.
6. Implement `api_service` to expose status.
7. Implement a minimal iPhone dashboard.

Once the above is stable, consider:

* Adding history logging and a basic `ml_service`.
* Adding more sophisticated animations on Teensy.
* Building the E-ink client script.

```

---

### How to actually feed this to Cursor

You don’t need *more* than these two to start:

- Put `ARCHITECTURE.md` and `SERVICES_AND_AGENTS.md` at the repo root.
- When you ask Cursor to build something (e.g., “implement `collector_service/main.py`”), reference them explicitly:
  - “Follow the design in ARCHITECTURE.md and SERVICES_AND_AGENTS.md.”

Later, if you want to get extra fancy, you could add:

- `PROTOCOLS.md` (if you keep evolving frame formats).
- `TODO.md` or `ROADMAP.md` with implementation tasks.

But these two are a solid “brain” for the project and contain all the details we’ve discussed.

If you want, next I can:

- Draft a starter `config_sync_service/main.py` skeleton,  
- Or a Teensy `.ino` skeleton that matches the frame format,  
so you have concrete code for Cursor to iterate on.
```
