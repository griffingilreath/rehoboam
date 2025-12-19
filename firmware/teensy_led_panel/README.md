# Teensy LED Status Panel

A modular project for driving a rack-mounted LED status display with a Teensy 4.x microcontroller and a host supervisor (Raspberry Pi, Jetson Nano, or Mac mini). The codebase is organized for clean separation between firmware animations, host side monitoring logic, and shared protocol documentation.

## Repository Layout

- `docs/` – architecture notes, state diagrams, communication protocol references.
- `firmware/` – Teensy source, header, and test code organized by role.
- `host/` – host-side supervisor scripts and services for monitoring systems.
- `shared/` – shared assets such as protocol definitions or lookup tables.
- `tools/` – auxiliary scripts for development, flashing, or diagnostics.

## Communication Protocol

The Teensy accepts two types of input over the USB serial connection:

1.  **JSON LED Frames**: The primary way to update the display. The host sends a single line containing a JSON object with the full state of the panel.
    ```json
    {"frame_id": 123456789, "leds": [{"i": 0, "h": 0, "a": 0.5, "t": 1}, ...]}
    ```
    - `i`: LED index (0-15)
    - `h`: Health code (0=OK, 1=WARN, 2=ERR, 3=OFFLINE, 4=UNKNOWN)
    - `a`: Activity level (0.0 - 1.0)
    - `t`: Activity type code

2.  **Text Commands**: Legacy/Debugging commands.
    - `READY`: Signals the host is ready.
    - `PING`: Keeps the connection alive (resets error state).
    - `STATE:LIVE` / `STATE:STANDBY`: Switches the display mode.
    - `ALARM:ID:ON` / `ALARM:ID:OFF`: Triggers or clears an alarm state.
    - `NOTIFY:TYPE:TTL_MS`: Enqueues a notification (e.g., `NOTIFY:warning:5000`). Supported types: `error`, `success`, `warning`.

## Dependencies

The firmware uses **PlatformIO** for dependency management.

- `FastLED`: For driving the WS2812B/Neopixel LEDs.
- `ArduinoJson`: For parsing the incoming JSON frames efficiently.

## Third-party references

- All stock FastLED/PJRC example sketches live under `third_party/teensy_examples/` at the repo root so we can point to upstream behavior without mixing it into the production firmware tree.
- If you need to compare against the Waveshare IT8951 tooling (for the matching e-paper display), fetch those repos under `third_party/it8951/`.

## Building and Flashing

```bash
cd firmware/teensy_led_panel
pio run --target upload
```
