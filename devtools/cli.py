#!/usr/bin/env python3
"""Lightweight CLI summary for Rehoboam data files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

DEFAULT_DATA_DIR = Path("data")
REPO_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Dict[str, Any] | List[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - debug helper
        print(f"Failed to read {path}: {exc}")
        return None


def summarize_status(status: Dict[str, Any]) -> None:
    leds = status.get("leds", []) if status else []
    print("\nLED PANEL")
    if not leds:
        print("  (no data)")
    for led in leds:
        name = led.get("name") or f"LED {led.get('index')}"
        health = led.get("health", "UNKNOWN")
        activity = led.get("activity_level", 0)
        print(f"  {name:<18} | {health:<8} | activity={activity:.2f} | type={led.get('type', 'n/a')}")

    context = status.get("context") if status else None
    if context:
        flags = context.get("flags", {})
        print("\nCONTEXT")
        print(f"  Daypart: {context.get('daypart', 'n/a')}")
        print(f"  Occupied: {flags.get('occupied')}")
        print(f"  Rain expected: {flags.get('rain_expected')}")


def summarize_divergence(divergence: Dict[str, Any]) -> None:
    print("\nDIVERGENCE")
    if not divergence:
         print("  (no data)")
         return
    score = divergence.get("score")
    level = divergence.get("level")
    print(f"  Score: {score}  Level: {level}")
    recs = divergence.get("recommendations", [])
    if recs:
        print("  Recommendations:")
        for rec in recs[:5]:
            print(f"    - {rec.get('suggestion')} → {rec.get('target')} (trigger={rec.get('trigger')}, conf={rec.get('confidence')})")


def summarize_events(events_path: Path) -> None:
    data = load_json(events_path)
    events = data.get("events", []) if isinstance(data, dict) else []
    print("\nRECENT EVENTS")
    if not events:
        print("  (none)")
        return
    for evt in events[-5:][::-1]:
        print(f"  {evt.get('timestamp')} | {evt.get('friendly_name') or evt.get('entity_id')} | {evt.get('summary')}")


def export_ha_helpers(output_path: Path | None = None, use_current_config: bool = False) -> int:
    """Export Home Assistant helpers configuration file."""
    example_path = REPO_ROOT / "docs" / "home_assistant_helpers.example.yaml"
    
    if not example_path.exists():
        print(f"ERROR: Example file not found: {example_path}", file=sys.stderr)
        return 1
    
    # Read the example file
    try:
        content = example_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: Failed to read {example_path}: {exc}", file=sys.stderr)
        return 1
    
    # Optionally merge in current values from led_config.json
    # (only if requested, otherwise preserve original comments)
    if use_current_config:
        if not HAS_YAML:
            print("WARNING: PyYAML not available, cannot merge current config", file=sys.stderr)
            print("         Install with: pip install PyYAML", file=sys.stderr)
            print("         Exporting example file as-is.", file=sys.stderr)
        else:
            config_path = REPO_ROOT / DEFAULT_DATA_DIR / "led_config.json"
            if config_path.exists():
                try:
                    config_data = load_json(config_path)
                    if isinstance(config_data, dict) and "leds" in config_data:
                        # Parse the YAML content
                        ha_config = yaml.safe_load(content)
                        if not isinstance(ha_config, dict):
                            raise ValueError("Invalid YAML structure")
                        
                        # Update values from current config
                        for led in config_data["leds"]:
                            index = led.get("index", -1)
                            if index < 0 or index > 15:
                                continue
                            
                            # Update input_text fields
                            if "input_text" not in ha_config:
                                ha_config["input_text"] = {}
                            
                            name = led.get("name", "")
                            if name and f"led{index}_name" in ha_config["input_text"]:
                                ha_config["input_text"][f"led{index}_name"]["initial"] = name
                            
                            ip = led.get("ip", "")
                            if ip and f"led{index}_ip" in ha_config["input_text"]:
                                ha_config["input_text"][f"led{index}_ip"]["initial"] = ip
                            
                            ha_avail = led.get("ha_availability_entity", "")
                            if ha_avail and f"led{index}_ha_availability_entity" in ha_config["input_text"]:
                                ha_config["input_text"][f"led{index}_ha_availability_entity"]["initial"] = ha_avail
                            
                            event_entities = led.get("event_entities", "")
                            if event_entities:
                                if isinstance(event_entities, list):
                                    event_entities = ", ".join(event_entities)
                                if f"led{index}_event_entities" in ha_config["input_text"]:
                                    ha_config["input_text"][f"led{index}_event_entities"]["initial"] = event_entities
                            
                            # Update input_select type
                            led_type = led.get("type", "")
                            if led_type and "input_select" in ha_config and f"led{index}_type" in ha_config["input_select"]:
                                ha_config["input_select"][f"led{index}_type"]["initial"] = led_type
                        
                        # Re-serialize to YAML
                        content = yaml.safe_dump(ha_config, sort_keys=False, default_flow_style=False, allow_unicode=True)
                except Exception as exc:
                    print(f"WARNING: Could not merge current config: {exc}", file=sys.stderr)
                    print("         Exporting example file as-is.", file=sys.stderr)
    
    # Write to output
    if output_path:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            print(f"✓ Exported Home Assistant helpers configuration to: {output_path}")
            print(f"\nNext steps:")
            print(f"  1. Copy this file into your Home Assistant configuration")
            print(f"  2. Restart Home Assistant")
            print(f"  3. Configure values via Settings → Devices & Services → Helpers")
            return 0
        except Exception as exc:
            print(f"ERROR: Failed to write {output_path}: {exc}", file=sys.stderr)
            return 1
    else:
        # Output to stdout
        print(content, end="")
        return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dev CLI for Rehoboam data files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View current system status
  python devtools/cli.py

  # Export HA helpers config to a file
  python devtools/cli.py export-ha-config --output helpers.yaml

  # Export with current values from led_config.json
  python devtools/cli.py export-ha-config --output helpers.yaml --use-current-config

  # Export to stdout (pipe to file)
  python devtools/cli.py export-ha-config > helpers.yaml
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Status command (default)
    status_parser = subparsers.add_parser("status", help="Show current system status (default)")
    status_parser.add_argument("--data", default=str(DEFAULT_DATA_DIR), help="Path to data directory")
    
    # Export HA config command
    export_parser = subparsers.add_parser(
        "export-ha-config",
        help="Export Home Assistant helpers configuration file"
    )
    export_parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file path (default: stdout)"
    )
    export_parser.add_argument(
        "--use-current-config",
        action="store_true",
        help="Merge current values from data/led_config.json into the export"
    )
    
    args = parser.parse_args(argv)
    
    # Default to status if no command specified
    if args.command is None:
        args.command = "status"
    
    if args.command == "status":
        data_dir = Path(getattr(args, "data", DEFAULT_DATA_DIR))
        status = load_json(data_dir / "canonical_state.json") or load_json(data_dir / "raw_state.json")
        summarize_status(status or {})

        divergence = load_json(data_dir / "divergence.json") or {}
        summarize_divergence(divergence)

        summarize_events(data_dir / "events.json")
        return 0
    
    elif args.command == "export-ha-config":
        return export_ha_helpers(
            output_path=getattr(args, "output", None),
            use_current_config=getattr(args, "use_current_config", False)
        )
    
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
