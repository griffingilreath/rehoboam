import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


class ConfigExamplesTest(unittest.TestCase):
    def test_examples_parse(self):
        config_files = sorted((REPO_ROOT / "jetson").glob("*/config.example.yaml"))
        self.assertTrue(config_files, "No config.example.yaml files found")
        for cfg in config_files:
            data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict, f"Config {cfg} should be a mapping")
            parts = set(cfg.parts)
            if "config_sync_service" in parts:
                self.assertIn("home_assistant", data)
            if "collector_service" in parts:
                self.assertIn("home_assistant", data)
                self.assertIn("pihole", data)
            if "state_engine_service" in parts:
                self.assertIn("health_rules", data)
                self.assertIn("activity_rules", data)
            if "led_encoder_service" in parts:
                self.assertIn("serial_device", data)
            if "api_service" in parts:
                self.assertIn("host", data)
                self.assertIn("port", data)


if __name__ == "__main__":
    unittest.main()
