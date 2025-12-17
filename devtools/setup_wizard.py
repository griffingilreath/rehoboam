#!/usr/bin/env python3
"""
Interactive menu-based setup wizard for Rehoboam services.

Run this over SSH from the repo root:

    python devtools/setup_wizard.py

Features:
- Interactive menu system: Select what to configure (HA, Pi-hole, API, LED encoder, e-paper)
- Configuration summary: View current settings at any time
- Smart defaults: Shows existing values - press Enter to keep them
- Selective updates: Configure only what you need
- Status indicators: Menu shows ✓/✗ for each configured section
- Full setup option: Configure everything in one pass

The wizard will:
- Load existing configuration from `.env` and `config.yaml` files
- Show configuration summary on startup (optional, if config exists)
- Display interactive menu with status indicators
- Allow selective configuration of each section
- Preserve existing values when you press Enter
- Write `.env` file (HA_BASE_URL, HA_TOKEN, PIHOLE_BASE_URL, PIHOLE_TOKEN)
- Ensure `jetson/*/config.yaml` files exist (copying from `config.example.yaml` if needed)
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    # Requests is required for validation but script can run without it
    requests = None


REPO_ROOT = Path(__file__).resolve().parents[1]


def prompt(text: str, default: str | None = None, secret: bool = False) -> str:
    """Prompt for input with optional default value.
    
    If default is provided and user presses Enter, returns default.
    If secret=True and default exists, shows placeholder instead of actual value.
    """
    if secret and default:
        # For secrets, show placeholder instead of actual value
        suffix = " [***existing***]" if default else ""
    else:
        suffix = f" [{default}]" if default is not None else ""
    
    while True:
        raw = input(f"{text}{suffix}: ")
        value = raw.strip()
        
        # If user pressed Enter and we have a default, use it
        if not value and default is not None:
            return default
        
        # If user entered something, use it (even if empty string to clear)
        if value or default is None:
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


def load_env_file(env_path: Path) -> dict[str, str]:
    """Load existing .env file and return as dict."""
    if not env_path.exists():
        return {}
    result: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result[key.strip()] = value.strip()
    return result


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


def load_all_configs() -> tuple[dict[str, str], dict, dict, dict]:
    """Load all existing configuration files."""
    env_path = REPO_ROOT / ".env"
    existing_env = load_env_file(env_path)
    
    api_cfg = REPO_ROOT / "jetson" / "api_service" / "config.yaml"
    existing_api = {}
    if api_cfg.exists():
        try:
            existing_api = yaml.safe_load(api_cfg.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    
    led_cfg = REPO_ROOT / "jetson" / "led_encoder_service" / "config.yaml"
    existing_led = {}
    if led_cfg.exists():
        try:
            existing_led = yaml.safe_load(led_cfg.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    
    epaper_cfg = REPO_ROOT / "epaper" / "config.yaml"
    existing_epaper = {}
    if epaper_cfg.exists():
        try:
            existing_epaper = yaml.safe_load(epaper_cfg.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    
    return existing_env, existing_api, existing_led, existing_epaper


def show_config_summary(existing_env: dict[str, str], existing_api: dict, existing_led: dict, existing_epaper: dict) -> None:
    """Display a summary of current configuration."""
    print("\n" + "="*60)
    print("Current Configuration Summary")
    print("="*60)
    
    # Home Assistant
    ha_url = existing_env.get("HA_BASE_URL", "Not configured")
    ha_token = "✓ Set" if existing_env.get("HA_TOKEN") else "✗ Not set"
    print(f"\nHome Assistant:")
    print(f"  URL: {ha_url}")
    print(f"  Token: {ha_token}")
    
    # Pi-hole
    pihole_url = existing_env.get("PIHOLE_BASE_URL", "Not configured")
    pihole_token = "✓ Set" if existing_env.get("PIHOLE_TOKEN") else "✗ Not set"
    print(f"\nPi-hole:")
    print(f"  URL: {pihole_url}")
    print(f"  Token: {pihole_token}")
    
    # API Service
    api_port = existing_api.get("port", "Not configured")
    cors_origins = existing_api.get("cors_origins", [])
    print(f"\nAPI Service:")
    print(f"  Port: {api_port}")
    print(f"  CORS Origins: {', '.join(cors_origins) if cors_origins else 'None'}")
    
    # LED Encoder
    serial_dev = existing_led.get("serial_device", "Not configured")
    print(f"\nLED Encoder:")
    print(f"  Serial Device: {serial_dev}")
    
    # E-paper
    if existing_epaper:
        backend = existing_epaper.get("backend", "Not configured")
        print(f"\nE-paper:")
        print(f"  Backend: {backend}")
    
    print("="*60 + "\n")


def show_main_menu(existing_env: dict[str, str], existing_api: dict, existing_led: dict, existing_epaper: dict) -> str:
    """Display main menu and return user's choice."""
    print("\n" + "="*60)
    print("Rehoboam Setup Wizard")
    print("="*60)
    
    # Show quick status indicators
    ha_status = "✓" if existing_env.get("HA_BASE_URL") and existing_env.get("HA_TOKEN") else "✗"
    pihole_status = "✓" if existing_env.get("PIHOLE_BASE_URL") else "✗"
    api_status = "✓" if existing_api.get("port") else "✗"
    led_status = "✓" if existing_led.get("serial_device") else "✗"
    epaper_status = "✓" if existing_epaper.get("backend") else "✗"
    
    print("\nWhat would you like to configure?")
    print()
    print(f"  {ha_status} 1. Home Assistant settings")
    print(f"  {pihole_status} 2. Pi-hole settings")
    print(f"  {api_status} 3. API & Dashboard settings")
    print(f"  {led_status} 4. LED Encoder / Teensy settings")
    print(f"  {epaper_status} 5. E-paper display settings")
    print("    6. View current configuration summary")
    print("    7. Run full setup (configure everything)")
    print("    0. Exit")
    print()
    
    while True:
        choice = input("Select an option [0-7]: ").strip()
        if choice in ["0", "1", "2", "3", "4", "5", "6", "7"]:
            return choice
        print("Invalid option. Please enter 0-7.")


def validate_ha_connection(base_url: str, token: str) -> None:
    """Attempt to connect to Home Assistant and verify credentials."""
    if not requests:
        return
    
    print("\n  Verifying connection to Home Assistant...")
    
    # Clean URL
    url = base_url.rstrip("/")
    api_url = f"{url}/api/"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    try:
        # Create a session with short timeout for validation
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=1)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        response = session.get(api_url, headers=headers, timeout=3.0)
        
        if response.status_code == 200:
            print(f"  ✓ Success! Connected to {response.json().get('message', 'Home Assistant API')}")
        elif response.status_code == 401:
            print("  ⚠️  Authentication failed (401 Unauthorized). Check your token.")
        elif response.status_code == 404:
            print(f"  ⚠️  Endpoint not found at {api_url}. Check base URL.")
        else:
            print(f"  ⚠️  Unexpected status: {response.status_code}")
            
    except Exception as e:
        print(f"  ⚠️  Connection failed: {e}")
    print("")


def configure_home_assistant(existing_env: dict[str, str]) -> dict[str, str]:
    """Configure Home Assistant settings."""
    print("\n" + "="*60)
    print("Home Assistant Configuration")
    print("="*60)
    
    ha_base_default = existing_env.get("HA_BASE_URL", "http://homeassistant.local:8123")
    ha_base = prompt("Home Assistant base URL", ha_base_default)
    
    ha_token_default = existing_env.get("HA_TOKEN", "")
    ha_token_prompt = "Home Assistant long-lived token (paste)"
    if ha_token_default:
        ha_token_prompt += " (press Enter to keep existing)"
    ha_token = prompt(ha_token_prompt, default=ha_token_default if ha_token_default else None, secret=True)
    
    if ha_base and ha_token:
        validate_ha_connection(ha_base, ha_token)
    
    return {"HA_BASE_URL": ha_base, "HA_TOKEN": ha_token}


def validate_pihole_connection(base_url: str, token: str) -> None:
    """Attempt to connect to Pi-hole and verify reachability."""
    if not requests:
        return
        
    print("\n  Verifying connection to Pi-hole...")
    url = base_url.rstrip("/")
    # Try legacy v5 endpoint which is most common
    api_url = f"{url}/admin/api.php"
    params = {"summaryRaw": 1}
    if token:
        params["auth"] = token
        
    try:
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=1)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        response = session.get(api_url, params=params, timeout=3.0)
        
        if response.status_code == 200:
            try:
                data = response.json()
                if "status" in data:
                    print(f"  ✓ Success! Connected to Pi-hole (Status: {data.get('status')})")
                else:
                    print("  ✓ Connected, but response format unexpected (might be v6 or custom).")
            except Exception:
                print("  ✓ Connected, but response was not JSON.")
        elif response.status_code == 404:
            print(f"  ⚠️  Endpoint not found at {api_url}. If using v6, this is expected (setup assumes v5 path).")
        else:
            print(f"  ⚠️  Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"  ⚠️  Connection failed: {e}")
    print("")


def configure_pihole(existing_env: dict[str, str]) -> dict[str, str]:
    """Configure Pi-hole settings."""
    print("\n" + "="*60)
    print("Pi-hole Configuration")
    print("="*60)
    
    has_pihole_config = bool(existing_env.get("PIHOLE_BASE_URL"))
    use_pihole = confirm("Configure Pi-hole integration?", default=has_pihole_config or True)
    
    if not use_pihole:
        return {}
    
    pihole_base_default = existing_env.get("PIHOLE_BASE_URL", "http://pihole.local")
    pihole_base = prompt("Pi-hole base URL", pihole_base_default)
    
    pihole_token_default = existing_env.get("PIHOLE_TOKEN", "")
    pihole_token_prompt = "Pi-hole API token (leave blank if none)"
    if pihole_token_default:
        pihole_token_prompt += " (press Enter to keep existing)"
    pihole_token = prompt(pihole_token_prompt, default=pihole_token_default if pihole_token_default else None, secret=True)
    
    if pihole_base:
        validate_pihole_connection(pihole_base, pihole_token)
    
    return {"PIHOLE_BASE_URL": pihole_base, "PIHOLE_TOKEN": pihole_token}


def configure_api_dashboard(existing_api: dict) -> None:
    """Configure API and dashboard settings."""
    print("\n" + "="*60)
    print("API & Dashboard Configuration")
    print("="*60)
    print(
        "- API port: where FastAPI listens on the Jetson (8000 is the default used in docs/systemd).\n"
        "- Dashboard origin: the URL you load the dashboard from (only needed if it is on a different\n"
        "  host/port than the API, to allow CORS). If you are unsure, just press Enter to keep defaults."
    )
    
    current_api_port = str(existing_api.get("port", 8000))
    api_port_prompt = f"API port for jetson/api_service (Press Enter to keep {current_api_port})"
    api_port = prompt(api_port_prompt, default=current_api_port)
    
    existing_origins = existing_api.get("cors_origins", [])
    dashboard_origin_default = existing_origins[0] if existing_origins else ""
    dashboard_origin_prompt = "Dashboard origin URL for CORS (e.g., http://iphone-rack.local, leave blank if unsure)"
    if dashboard_origin_default:
        dashboard_origin_prompt += f" (press Enter to keep: {dashboard_origin_default})"
    dashboard_origin = prompt(dashboard_origin_prompt, default=dashboard_origin_default if dashboard_origin_default else None)
    
    # Ensure config exists
    ensure_service_config(REPO_ROOT / "jetson" / "api_service")
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


def configure_led_encoder(existing_led: dict) -> None:
    """Configure LED encoder / Teensy settings."""
    print("\n" + "="*60)
    print("LED Encoder / Teensy Configuration")
    print("="*60)
    print(
        "- The service can auto-detect the Teensy serial port when 'serial_device' is set to 'auto'.\n"
        "- If you prefer to pin a specific device (e.g., /dev/ttyACM0), enter it below; otherwise\n"
        "  just press Enter to keep current setting.\n"
        "- Note: On Linux, you may need to add your user to the 'dialout' group for serial access:\n"
        "  sudo usermod -a -G dialout $USER (then log out/in or reboot)"
    )
    
    current_serial = existing_led.get("serial_device", "auto")
    serial_dev_prompt = f"Serial device for Teensy (Press Enter to keep: {current_serial})"
    serial_dev = prompt(serial_dev_prompt, default=current_serial)
    
    # Ensure config exists
    ensure_service_config(REPO_ROOT / "jetson" / "led_encoder_service")
    led_cfg = REPO_ROOT / "jetson" / "led_encoder_service" / "config.yaml"
    
    def _update_led(cfg: dict) -> bool:
        changed_local = False
        if serial_dev and cfg.get("serial_device") != serial_dev:
            cfg["serial_device"] = serial_dev
            changed_local = True
        return changed_local
    
    update_yaml(led_cfg, _update_led)
    
    # Optional: LED panel test
    if confirm("Would you like to test the LED panel now? (lights each LED one at a time)", default=False):
        print("\nStarting LED panel test...")
        print("This will help you verify the connection and map LEDs to ports.")
        print("Note: If you get permission errors, you may need to add your user to the 'dialout' group.")
        print("      Run: sudo usermod -a -G dialout $USER (then log out/in)")
        print("\nThe test will:")
        print("  - Light each LED sequentially (0-15)")
        print("  - Ask you to identify which physical port it corresponds to (R1-R8, S1-S8)")
        print("  - Save the mapping to data/led_mapping.json")
        print("\nNote: LED port names/descriptions are configured via Home Assistant helpers.")
        print("      Use 'python devtools/cli.py export-ha-config' to generate the HA config.\n")
        
        import subprocess
        test_script = REPO_ROOT / "devtools" / "test_led_panel.py"
        if test_script.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(test_script), "--device", serial_dev],
                    check=False,
                    capture_output=False,
                )
                if result.returncode != 0:
                    print("\n⚠️  LED panel test failed. This is okay - you can:")
                    print("   1. Fix permissions and run the test later:")
                    print(f"      python devtools/test_led_panel.py --device {serial_dev}")
                    print("   2. Skip the test for now and configure LEDs via Home Assistant helpers")
                    print("   3. The LED encoder service will work once permissions are fixed")
            except KeyboardInterrupt:
                print("\n✓ Test cancelled - you can run it later with:")
                print(f"  python devtools/test_led_panel.py --device {serial_dev}")
            except Exception as exc:
                print(f"\n⚠️  Could not run LED panel test: {exc}")
                print("   You can run it manually later with:")
                print(f"   python devtools/test_led_panel.py --device {serial_dev}")
        else:
            print(f"Warning: {test_script} not found. Run it manually with:")
            print(f"  python devtools/test_led_panel.py --device {serial_dev}")


def configure_epaper(existing_epaper: dict) -> None:
    """Configure e-paper display settings."""
    print("\n" + "="*60)
    print("E-paper Display Configuration")
    print("="*60)
    
    epaper_cfg = REPO_ROOT / "epaper" / "config.yaml"
    if not (REPO_ROOT / "epaper").exists():
        print("E-paper module not found. Skipping.")
        return
    
    current_backend = existing_epaper.get("backend", "fake")
    backend_prompt = f"E-paper backend (fake/spi/usb, Enter to keep: {current_backend})"
    backend = prompt(backend_prompt, default=current_backend).lower()
    
    def _update_epaper(cfg: dict) -> bool:
        changed_local = False
        if backend in {"fake", "spi", "usb"} and cfg.get("backend") != backend:
            cfg["backend"] = backend
            changed_local = True
        return changed_local
    
    ensure_service_config(REPO_ROOT / "epaper")
    epaper_cfg = REPO_ROOT / "epaper" / "config.yaml"
    update_yaml(epaper_cfg, _update_epaper)


def main() -> None:
    print("Rehoboam setup wizard\n")
    
    # Load existing configuration
    existing_env, existing_api, existing_led, existing_epaper = load_all_configs()
    
    # Check if we have existing config
    has_existing = bool(existing_env or existing_api or existing_led or existing_epaper)
    
    # Show summary on first run if config exists
    if has_existing:
        print("✓ Found existing configuration")
        if confirm("View configuration summary before starting?", default=True):
            show_config_summary(existing_env, existing_api, existing_led, existing_epaper)
    
    while True:
        choice = show_main_menu(existing_env, existing_api, existing_led, existing_epaper)
        
        if choice == "0":
            print("\nExiting setup wizard.")
            break
        elif choice == "1":
            env_updates = configure_home_assistant(existing_env)
            existing_env.update(env_updates)
            env_path = REPO_ROOT / ".env"
            write_env_file(env_path, existing_env)
            print("\n✓ Home Assistant configuration updated")
        elif choice == "2":
            env_updates = configure_pihole(existing_env)
            if env_updates:
                # Pi-hole enabled - update config
                existing_env.update(env_updates)
                env_path = REPO_ROOT / ".env"
                write_env_file(env_path, existing_env)
                print("\n✓ Pi-hole configuration updated")
            else:
                # Pi-hole disabled - remove from env
                existing_env.pop("PIHOLE_BASE_URL", None)
                existing_env.pop("PIHOLE_TOKEN", None)
                env_path = REPO_ROOT / ".env"
                write_env_file(env_path, existing_env)
                print("\n✓ Pi-hole integration disabled")
        elif choice == "3":
            configure_api_dashboard(existing_api)
            _, existing_api, _, _ = load_all_configs()  # Reload to get updated values
            print("\n✓ API & Dashboard configuration updated")
        elif choice == "4":
            configure_led_encoder(existing_led)
            _, _, existing_led, _ = load_all_configs()  # Reload to get updated values
            print("\n✓ LED Encoder configuration updated")
        elif choice == "5":
            configure_epaper(existing_epaper)
            _, _, _, existing_epaper = load_all_configs()  # Reload to get updated values
            print("\n✓ E-paper configuration updated")
        elif choice == "6":
            show_config_summary(existing_env, existing_api, existing_led, existing_epaper)
            input("\nPress Enter to continue...")
        elif choice == "7":
            # Full setup - configure everything
            print("\n" + "="*60)
            print("Full Setup - Configuring All Settings")
            print("="*60)
            
            # Ensure service configs exist
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
            
            # Configure each section
            env_updates = configure_home_assistant(existing_env)
            existing_env.update(env_updates)
            
            pihole_updates = configure_pihole(existing_env)
            existing_env.update(pihole_updates)
            
            env_path = REPO_ROOT / ".env"
            if env_updates or pihole_updates:
                write_env_file(env_path, existing_env)
            else:
                print(f"✓ .env file unchanged: {env_path}")
            
            configure_api_dashboard(existing_api)
            configure_led_encoder(existing_led)
            configure_epaper(existing_epaper)
            
            print(
                "\n" + "="*60 +
                "\n✓ Full setup complete!\n"
                "- The `.env` file now holds your HA/Pi-hole secrets (used for local/dev runs).\n"
                "- Each service has a `config.yaml` you can fine-tune.\n"
                "- API port, CORS origins, serial device, and (optionally) e-paper backend were configured.\n"
                "For rack deployment, copy configs to `/etc/rehoboam/*.yaml` and secrets to `/etc/rehoboam/secrets.env` as described in the README."
            )
            
            if not confirm("\nReturn to main menu?", default=False):
                break


if __name__ == "__main__":
    main()


