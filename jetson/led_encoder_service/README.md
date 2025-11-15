# led_encoder_service

Reads `canonical_state.json` and streams compact LED frames to the Teensy microcontroller over serial. This is the final glue between the Jetson’s canonical model and the physical LED strip.

## Responsibilities

- Poll `canonical_state.json` at a fixed cadence.
- Convert each LED entry into compact integers (`health`, `activity_type`, etc.).
- Write JSON frames to the serial device expected by the Teensy firmware.
- Avoid redundant writes by caching the last serialized frame.
- Provide a `--dry-run` mode for development (prints frames to stdout).

## Prerequisites

- Python 3.9+ and `pip install -r jetson/requirements.txt` (needs `pyserial`).
- Teensy connected to the Jetson (`/dev/ttyACM*` or similar) with matching baud rate.
- Upstream services (`state_engine_service`) producing `canonical_state.json` in the shared data directory.

## Configuration

1. Copy and edit:
   ```bash
   cp jetson/led_encoder_service/config.example.yaml jetson/led_encoder_service/config.yaml
   ```
2. Fields:
   - `data_dir`: location of shared JSON files.
   - `canonical_state_filename`: usually `canonical_state.json`.
   - `serial_device`: `/dev/ttyACM0` (Linux), `/dev/cu.usbmodem...` (macOS), or COM port on Windows.
   - `baud_rate`: must match the Teensy sketch.
   - `frame_interval_seconds`: send frames every N seconds (0.2 = 5 fps). Teensy can interpolate for smoother motion.
   - `health_code_map`: mapping from canonical `health` strings to small ints recognized by firmware.
   - `activity_type_map`: similar mapping for activity types; add custom entries if your firmware supports more effects.

## Running

```bash
python jetson/led_encoder_service/main.py \
  --config jetson/led_encoder_service/config.yaml
```

- Add `--dry-run` to print frames instead of using serial (perfect for unit tests or dashboard prototyping).
- Override log level with `--log-level DEBUG` to inspect every frame.

## Frame Format

Frames follow the structure laid out in `SERVICES_AND_AGENTS.md`:

```json
{
  "frame_id": 1731615300,
  "timestamp": 1731615300,
  "leds": [
    {"i": 0, "h": 0, "a": 0.42, "t": 1},
    {"i": 1, "h": 2, "a": 0.05, "t": 0}
  ]
}
```

- `i`: LED index (0–15).
- `h`: health code from `health_code_map`.
- `a`: activity level (0–1 float, rounded to three decimals).
- `t`: activity type code from `activity_type_map`.

Each JSON frame is newline-delimited so the Teensy parser can read line-by-line.

## Operational Notes

- Frames are only sent when the payload changes, reducing unnecessary serial traffic.
- If the serial device disappears (USB cable unplugged), the service logs an error and keeps retrying.
- Use `systemd`/`supervisor` to keep the process alive; on crash it exits and will be restarted by your init system.
- When `canonical_state.json` is missing or malformed, the service logs a warning and waits for the next interval.
- Keep the frame interval aligned with Teensy expectations; very high frame rates can saturate the serial link without benefit.
- Successful frame transmissions update `service_health.json` so `/health` always reflects encoder status.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Unable to open serial device` | Wrong device path or permissions | Use `ls /dev/tty*`, add user to `dialout`, or update config |
| Frames printed but LEDs static | Running with `--dry-run` | Remove flag to use serial |
| Teensy not parsing frames | Firmware expects different mapping | Align `health_code_map` / `activity_type_map` with firmware enums |
| High latency / drops | Frame interval too low or USB bottleneck | Increase `frame_interval_seconds` |

## Extending

- Compress frames further (e.g., binary) by swapping `_build_frame` and the Teensy decoder simultaneously.
- Add optional CRC or checksum fields for more robust serial transmission.
- Expose a WebSocket mirror so dashboards can preview LED output without reading `canonical_state.json`.

## Next Step

With the encoder running, the LED panel reflects canonical state in real time. Next services to build: `api_service` for dashboards and (eventually) ML or history logging as described in `SERVICES_AND_AGENTS.md`.
