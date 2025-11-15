# Firmware Overview

This directory contains the Teensy firmware organized for PlatformIO.

## Layout
- `src/` – primary application sources (`main.cpp`, state machine, animation drivers).
- `include/` – shared headers and configuration structs.
- `lib/` – third-party or reusable libraries vendored for the project.
- `test/` – PlatformIO unit tests (Unity) covering state and protocol logic.
- `src/animations/` – individual animation implementations (startup, standby, notification, alarm).
- `src/controllers/` – managers for state machine, protocol handling, and LED drivers.

## Getting Started
1. Install PlatformIO (`pip install platformio`) or use the VS Code extension.
2. Use `pio run -e teensy32` to build, `pio test -e teensy32` for unit tests, and `pio run -e teensy32 --target upload` to flash the Teensy 3.2.
3. Adjust configuration values in `include/config.hpp` (created later) to tune timings and LED brightness.

## Hardware Smoke Test
- Build the `teensy32_led_test` PlatformIO environment to sanity-check wiring before flashing the full firmware.
- The sketch cycles through red, green, blue, white on the first pixel, then runs a rainbow chase across up to 16 LEDs. A single LED connected will still display the first four steps, confirming solder joints and orientation before expanding the chain.
- Adjust `LED_COUNT`, `LED_PIN`, or `BRIGHTNESS` in `firmware/examples/basic_led_test/main.cpp` if your setup differs.
