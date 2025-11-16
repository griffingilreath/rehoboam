#!/usr/bin/env python3
"""
LED Panel Test & Calibration Tool

This tool helps you:
1. Verify the Teensy connection
2. Test each LED individually
3. Map physical LEDs to port numbers (R1-R8, S1-S8)

Usage:
    python devtools/test_led_panel.py [--device /dev/ttyACM0] [--baud 115200]

The tool will:
- Light each LED one at a time (0-15)
- Ask you to identify which port it corresponds to
- Save the mapping for reference
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

import serial

# Port mapping reference (for display)
PORT_NAMES = {
    0: "R1 - Ethernet In",
    1: "R2 - Rehoboam (Jetson/Teensy)",
    2: "R3 - Pi-hole",
    3: "R4 - Pi-Drive / NAS",
    4: "R5 - Mac Mini",
    5: "R6 - Airport Express",
    6: "R7 - Eero",
    7: "R8 - Switch to Switch",
    8: "S1 - Hue",
    9: "S2 - Lutron",
    10: "S3 - Ikea",
    11: "S4 - Aqara",
    12: "S5 - Starling",
    13: "S6 - Home Assistant",
    14: "S7 - Eufy",
    15: "S8 - Switch to Switch",
}


def find_teensy_port(device: Optional[str] = None) -> Optional[str]:
    """Auto-detect Teensy serial port."""
    if device and device != "auto":
        return device
    import glob
    # Prefer /dev/serial/by-id entries mentioning Teensy
    by_id = glob.glob("/dev/serial/by-id/*Teensy*") + glob.glob("/dev/serial/by-id/*teensy*")
    if by_id:
        try:
            real = Path(by_id[0]).resolve()
            return str(real)
        except OSError:
            return by_id[0]
    # Fallback to first ttyACM* or ttyUSB*
    for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*"):
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
    return None


def send_frame(ser: serial.Serial, led_index: int, health: int = 0, activity: float = 1.0, activity_type: int = 0) -> None:
    """Send a single LED frame to the Teensy."""
    frame = {
        "frame_id": int(time.time()),
        "timestamp": int(time.time()),
        "leds": [{"i": led_index, "h": health, "a": activity, "t": activity_type}],
    }
    payload = json.dumps(frame, separators=(",", ":")) + "\n"
    ser.write(payload.encode("utf-8"))
    ser.flush()


def clear_all(ser: serial.Serial) -> None:
    """Turn off all LEDs."""
    frame = {
        "frame_id": int(time.time()),
        "timestamp": int(time.time()),
        "leds": [{"i": i, "h": 0, "a": 0.0, "t": 0} for i in range(16)],
    }
    payload = json.dumps(frame, separators=(",", ":")) + "\n"
    ser.write(payload.encode("utf-8"))
    ser.flush()


def test_single_led(ser: serial.Serial, led_index: int) -> Optional[str]:
    """Light a single LED and ask the user to identify it."""
    print(f"\n{'='*60}")
    print(f"LED Index {led_index} is now LIT")
    print(f"Expected port: {PORT_NAMES.get(led_index, 'Unknown')}")
    print(f"{'='*60}")
    print("Look at your LED panel and identify which physical port this LED corresponds to.")
    print("Options:")
    print("  - Enter the port name (e.g., 'R1', 'S3', 'Ethernet In')")
    print("  - Enter 'skip' to move to the next LED")
    print("  - Enter 'quit' to exit")
    print("  - Press Enter to accept the expected port name")
    
    response = input("\nWhich port is this LED? ").strip()
    
    if response.lower() == "quit":
        return None
    if response.lower() == "skip":
        return "SKIPPED"
    if not response:
        return PORT_NAMES.get(led_index, f"LED_{led_index}")
    return response


def run_test_sequence(device: str, baud: int = 115200) -> dict[int, str]:
    """Run the full LED test sequence."""
    port = find_teensy_port(device)
    if not port:
        print("ERROR: Could not find Teensy serial port.")
        print("Please specify --device /dev/ttyACM0 (or similar)")
        sys.exit(1)
    
    print(f"Connecting to Teensy at {port} @ {baud} baud...")
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)  # Give Teensy time to initialize
        print("Connected!")
    except serial.SerialException as e:
        print(f"ERROR: Could not open serial port: {e}")
        sys.exit(1)
    
    mapping: dict[int, str] = {}
    
    try:
        print("\nStarting LED test sequence...")
        print("Each LED will light up one at a time.")
        print("You'll be asked to identify which port it corresponds to.\n")
        
        input("Press Enter to start...")
        
        # Test each LED sequentially
        for led_index in range(16):
            # Light this LED (health=OK, full activity)
            send_frame(ser, led_index, health=0, activity=1.0, activity_type=0)
            time.sleep(0.5)  # Give it time to light up
            
            port_name = test_single_led(ser, led_index)
            if port_name is None:
                print("\nTest cancelled by user.")
                break
            mapping[led_index] = port_name
            
            # Turn off this LED before moving to next
            send_frame(ser, led_index, health=0, activity=0.0, activity_type=0)
            time.sleep(0.3)
        
        # Clear all LEDs at the end
        clear_all(ser)
        print("\nAll LEDs cleared.")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted. Clearing LEDs...")
        clear_all(ser)
    finally:
        ser.close()
    
    return mapping


def save_mapping(mapping: dict[int, str], output_path: Path) -> None:
    """Save the LED-to-port mapping to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": "1.0",
        "mapping": {str(k): v for k, v in mapping.items()},
        "notes": "This mapping was generated by test_led_panel.py",
    }
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\nMapping saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test and calibrate the LED panel")
    parser.add_argument(
        "--device",
        default="auto",
        help="Serial device path (default: auto-detect)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Baud rate (default: 115200)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/led_mapping.json"),
        help="Output file for LED mapping (default: data/led_mapping.json)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test: just verify connection and light all LEDs",
    )
    
    args = parser.parse_args()
    
    if args.quick:
        # Quick connection test
        port = find_teensy_port(args.device)
        if not port:
            print("ERROR: Could not find Teensy serial port.")
            sys.exit(1)
        print(f"Connecting to {port}...")
        try:
            ser = serial.Serial(port, args.baud, timeout=1)
            time.sleep(2)
            print("Connected! Lighting all LEDs for 3 seconds...")
            # Light all LEDs
            frame = {
                "frame_id": int(time.time()),
                "timestamp": int(time.time()),
                "leds": [{"i": i, "h": 0, "a": 1.0, "t": 0} for i in range(16)],
            }
            payload = json.dumps(frame, separators=(",", ":")) + "\n"
            ser.write(payload.encode("utf-8"))
            ser.flush()
            time.sleep(3)
            clear_all(ser)
            ser.close()
            print("Test complete!")
        except serial.SerialException as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        return
    
    # Full interactive test
    mapping = run_test_sequence(args.device, args.baud)
    
    if mapping:
        print("\n" + "="*60)
        print("LED Mapping Results:")
        print("="*60)
        for led_index in sorted(mapping.keys()):
            print(f"  LED {led_index:2d} -> {mapping[led_index]}")
        
        if args.output:
            save_mapping(mapping, args.output)


if __name__ == "__main__":
    main()

