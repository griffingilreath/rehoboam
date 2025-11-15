import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_service_config_examples_parse():
    config_files = sorted((REPO_ROOT / "jetson").glob("*/config.example.yaml"))
    assert config_files, "No config.example.yaml files found"
    for cfg in config_files:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"Config {cfg} should be a mapping"
        # spot-check required sections depending on service
        if "config_sync_service" in cfg.parts:
            assert "home_assistant" in data
        if "collector_service" in cfg.parts:
            assert "home_assistant" in data and "pihole" in data
        if "state_engine_service" in cfg.parts:
            assert "health_rules" in data and "activity_rules" in data
        if "led_encoder_service" in cfg.parts:
            assert "serial_device" in data
        if "api_service" in cfg.parts:
            assert "host" in data and "port" in data
