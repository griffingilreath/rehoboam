#!/usr/bin/env python3
"""
Interactive setup helper for Rehoboam services.

Run this over SSH from the repo root:

    python devtools/setup_wizard.py

It will:
- Ask for Home Assistant and Pi-hole connection details.
- Write a `.env` file in the repo (HA_BASE_URL, HA_TOKEN, PIHOLE_BASE_URL, PIHOLE_TOKEN).
- Ensure `jetson/*/config.yaml` files exist (copying from `config.example.yaml` if needed).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def prompt(text: str, default: str | None = None, secret: bool = False) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{text}{suffix}: ")
        value = raw.strip() or (default or "")
        if value or default is not None:
            return value


def confirm(text: str, default: bool = True) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        raw = input(f"{text}{suffix}: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False


def write_env_file(env_path: Path, values: dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in values.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {env_path}")


def ensure_service_config(service_dir: Path) -> None:
    example = service_dir / "config.example.yaml"
    target = service_dir / "config.yaml"
    if target.exists():
        print(f"Config already present: {target}")
        return
    if not example.exists():
        print(f"Skipping {service_dir.name}: no config.example.yaml found")
        return
    shutil.copy(example, target)
    print(f"Created {target} from {example}")


def update_yaml(path: Path, updater) -> None:
    if not path.exists():
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    changed = updater(data)
    if changed:
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        print(f"Updated {path}")


def main() -> None:
    print("Rehoboam setup wizard\n")

    # Home Assistant
    ha_base = prompt("Home Assistant base URL", "http://homeassistant.local:8123")
    ha_token = prompt("Home Assistant long-lived token (paste)", default="", secret=True)

    # Pi-hole (optional)
    use_pihole = confirm("Configure Pi-hole integration?", default=True)
    pihole_base = ""
    pihole_token = ""
    if use_pihole:
        pihole_base = prompt("Pi-hole base URL", "http://pihole.local")
        pihole_token = prompt("Pi-hole API token (leave blank if none)", default="", secret=True)

    env_values: dict[str, str] = {
        "HA_BASE_URL": ha_base,
        "HA_TOKEN": ha_token,
    }
    if use_pihole:
        env_values["PIHOLE_BASE_URL"] = pihole_base
        env_values["PIHOLE_TOKEN"] = pihole_token

    # Write local .env (services will read this in dev; /etc/rehoboam/secrets.env is for rack deployment)
    env_path = REPO_ROOT / ".env"
    write_env_file(env_path, env_values)

    print("\nEnsuring per-service configs exist...")
    for name in [
        "config_sync_service",
        "collector_service",
        "state_engine_service",
        "led_encoder_service",
        "api_service",
        "ml_service",
    ]:
        ensure_service_config(REPO_ROOT / "jetson" / name)

    # Optional: API + dashboard tuning
    print("\nAPI / dashboard settings:")
    api_port = prompt("API port for jetson/api_service (Press Enter to keep 8000)", default="8000")
    dashboard_origin = prompt(
        "Dashboard origin URL for CORS (e.g., http://iphone-rack.local, leave blank to skip)",
        default="",
    )
    api_cfg = REPO_ROOT / "jetson" / "api_service" / "config.yaml"

    def _update_api(cfg: dict) -> bool:
        changed_local = False
        try:
            current_port = int(cfg.get("port", 8000))
        except Exception:
            current_port = 8000
        new_port = int(api_port) if api_port else current_port
        if new_port != current_port:
            cfg["port"] = new_port
            changed_local = True
        if dashboard_origin:
            origins = cfg.get("cors_origins") or []
            if dashboard_origin not in origins:
                origins.append(dashboard_origin)
                cfg["cors_origins"] = origins
                changed_local = True
        return changed_local

    update_yaml(api_cfg, _update_api)

    # Optional: LED encoder serial device
    print("\nLED encoder settings:")
    serial_dev = prompt("Serial device for Teensy (Press Enter to keep /dev/ttyACM0)", "/dev/ttyACM0")
    led_cfg = REPO_ROOT / "jetson" / "led_encoder_service" / "config.yaml"

    def _update_led(cfg: dict) -> bool:
        changed_local = False
        if serial_dev and cfg.get("serial_device") != serial_dev:
            cfg["serial_device"] = serial_dev
            changed_local = True
        return changed_local

    update_yaml(led_cfg, _update_led)

    # Optional: e-paper backend quick choice
    epaper_cfg = REPO_ROOT / "epaper" / "config.yaml"
    if (REPO_ROOT / "epaper").exists():
        print("\nE-paper settings (optional):")
        backend = prompt("E-paper backend (fake/spi/usb, Enter to keep fake)", "fake").lower()

        def _update_epaper(cfg: dict) -> bool:
            changed_local = False
            if backend in {"fake", "spi", "usb"} and cfg.get("backend") != backend:
                cfg["backend"] = backend
                changed_local = True
            return changed_local

        if not epaper_cfg.exists():
            example = REPO_ROOT / "epaper" / "config.example.yaml"
            if example.exists():
                shutil.copy(example, epaper_cfg)
                print(f"Created {epaper_cfg} from {example}")
        update_yaml(epaper_cfg, _update_epaper)

    print(
        "\nDone.\n"
        "- The `.env` file now holds your HA/Pi-hole secrets (used for local/dev runs).\n"
        "- Each service has a `config.yaml` you can fine-tune.\n"
        "- API port, CORS origins, serial device, and (optionally) e-paper backend were configured.\n"
        "For rack deployment, copy configs to `/etc/rehoboam/*.yaml` and secrets to `/etc/rehoboam/secrets.env` as described in the README."
    )


if __name__ == "__main__":
    main()


