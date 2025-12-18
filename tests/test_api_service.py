import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from jetson.api_service.main import ServiceConfig, create_app


def seed_file(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class ApiServiceTest(unittest.TestCase):
    def test_endpoints_with_sample_files(self):
        data_dir = Path(self._tmpdir())
        seed_file(
            data_dir / "canonical_state.json",
            {"schema_version": "1.0", "timestamp": 1, "generated_at": "2025-01-01T00:00:00Z", "leds": []},
        )
        seed_file(data_dir / "led_config.json", {"schema_version": "1.0", "generated_at": "now", "leds": []})
        seed_file(data_dir / "history.json", {"schema_version": "1.0", "entries": []})
        seed_file(
            data_dir / "service_health.json",
            {
                "schema_version": "1.0",
                "timestamp": "now",
                "services": [{"name": "collector_service", "status": "running"}],
            },
        )
        seed_file(
            data_dir / "divergence.json",
            {
                "schema_version": "1.0",
                "generated_at": "now",
                "timestamp": 123,
                "score": 0.1,
                "level": "normal",
                "metrics": {},
                "recommendations": [
                    {
                        "id": "test:close_blind",
                        "timestamp": 123,
                        "target": "Blind",
                        "suggestion": "Close",
                        "confidence": 0.7,
                        "status": "pending",
                    }
                ],
            },
        )
        seed_file(
            data_dir / "cognition.json",
            {
                "schema_version": "1.0",
                "generated_at": "now",
                "timestamp": 123,
                "source": {"kind": "external_orchestrator", "base_url": "http://example", "status": "ok"},
                "agents": [],
                "decisions": [],
                "approvals": [],
            },
        )
        seed_file(
            data_dir / "ai_recommendations.json",
            {
                "schema_version": "1.0",
                "generated_at": "now",
                "timestamp": 123,
                "recommendations": [{"id": "rec_1", "timestamp": 123, "suggestion": "Test", "status": "pending"}],
            },
        )
        seed_file(
            data_dir / "feedback.json",
            {"schema_version": "1.0", "generated_at": "now", "timestamp": 123, "feedback": []},
        )

        config = ServiceConfig(data_dir=data_dir)
        app = create_app(config)
        client = TestClient(app)

        self.assertEqual(client.get("/status").status_code, 200)
        self.assertEqual(client.get("/config").status_code, 200)
        self.assertEqual(client.get("/history").json()["entries"], [])
        self.assertEqual(client.get("/divergence").status_code, 200)
        rec_resp = client.get("/recommendations")
        self.assertEqual(rec_resp.status_code, 200)
        self.assertEqual(len(rec_resp.json()["recommendations"]), 1)
        self.assertEqual(client.get("/cognition").status_code, 200)
        self.assertEqual(client.get("/recommendations/ai").status_code, 200)
        self.assertEqual(client.get("/feedback").status_code, 200)
        merged = client.get("/recommendations/all").json()["recommendations"]
        self.assertGreaterEqual(len(merged), 2)

        ack = client.post("/recommendations/test:close_blind", json={"status": "applied"})
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(ack.json()["status"], "applied")
        self.assertTrue((data_dir / "recommendations_state.json").exists())

    def _tmpdir(self) -> str:
        from tempfile import TemporaryDirectory

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


if __name__ == "__main__":
    unittest.main()

