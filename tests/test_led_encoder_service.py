import unittest
from pathlib import Path

import yaml

from jetson.common.led_codes import ActivityType, HealthCode
from jetson.common.service_runner import RunnerOverrides
from jetson.led_encoder_service.main import load_service_config


class LedEncoderConfigTest(unittest.TestCase):
    def test_led_encoder_default_code_maps(self):
        tmp = self._tmpdir()
        cfg = {
            "data_dir": str(tmp),
            "canonical_state_filename": "canonical_state.json",
            "serial_device": "/dev/null",
            "baud_rate": 9600,
            "frame_interval_seconds": 0.5,
        }
        cfg_path = Path(tmp) / "encoder.yaml"
        cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

        config = load_service_config(cfg_path, RunnerOverrides(data_dir=Path(tmp)))

        self.assertEqual(config.health_code_map["UNKNOWN"], HealthCode.UNKNOWN)
        self.assertEqual(config.activity_type_map["none"], ActivityType.NONE)

    def _tmpdir(self) -> Path:
        from tempfile import TemporaryDirectory

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)


if __name__ == "__main__":
    unittest.main()

