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
