import json
import unittest
from pathlib import Path

from jetson.state_engine_service.main import (
    ActivityRules,
    HealthRules,
    ServiceConfig,
    StateEngineService,
)


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class StateEngineServiceTest(unittest.TestCase):
    def test_emits_canonical_snapshot(self):
        data_dir = Path(self._tmpdir())
        led_config = {
            "leds": [
                {
                    "index": 0,
                    "name": "Test LED",
                    "type": "bridge",
                    "ha_availability_entity": "binary_sensor.test",
                }
            ]
        }
        raw_state = {
            "timestamp": 1731900000,
            "devices": {
                "Test LED": {
                    "reachable": True,
                    "rtt_ms": 10,
                    "events_last_window": 2,
                }
            },
            "events": [],
            "context": {
                "timestamp": 1731900000,
                "daypart": "morning",
                "flags": {"occupied": True, "rain_expected": False},
            },
        }
        write_json(data_dir / "led_config.json", led_config)
        write_json(data_dir / "raw_state.json", raw_state)

        config = ServiceConfig(
            data_dir=data_dir,
            led_config_filename="led_config.json",
            raw_state_filename="raw_state.json",
            canonical_state_filename="canonical_state.json",
            poll_interval_seconds=1,
            health_rules=HealthRules(),
            activity_rules=ActivityRules(),
            history_enabled=False,
            history_filename="history.json",
            history_max_entries=10,
            history_retention_seconds=86400,
            log_level="INFO",
        )

        service = StateEngineService(config)
        service.process_once()

        canonical = json.loads((data_dir / "canonical_state.json").read_text(encoding="utf-8"))
        self.assertTrue(canonical["leds"])
        led_entry = canonical["leds"][0]
        self.assertEqual(led_entry["name"], "Test LED")
        self.assertIn("health", led_entry)

    def _tmpdir(self) -> Path:
        from tempfile import TemporaryDirectory

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)


if __name__ == "__main__":
    unittest.main()
