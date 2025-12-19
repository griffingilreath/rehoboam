import json
import unittest
from pathlib import Path

from jetson.ml_service.main import ServiceConfig, MlService


class MlServiceTest(unittest.TestCase):
    def test_process_once_writes_divergence(self):
        data_dir = Path(self._tmpdir())
        history = {
            "schema_version": "1.0",
            "entries": [
                {
                    "schema_version": "1.0",
                    "timestamp": 1735689600,
                    "generated_at": "2025-01-01T00:00:00Z",
                    "leds": [{"index": 0, "health": "OK", "activity_level": 0.1, "activity_type": "none"}],
                }
            ],
        }
        (data_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

        config = ServiceConfig(
            data_dir=data_dir,
            canonical_state_filename="canonical_state.json",
            history_filename="history.json",
            output_filename="divergence.json",
            feedback_filename="feedback.json",
            poll_interval_seconds=1.0,
            history_window_seconds=3600,
            baseline_days=1,
            zscore_threshold=2.5,
            log_level="INFO",
        )
        service = MlService(config)
        service.process_once()

        payload = json.loads((data_dir / "divergence.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertIn("score", payload)

    def _tmpdir(self) -> str:
        from tempfile import TemporaryDirectory

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


if __name__ == "__main__":
    unittest.main()

