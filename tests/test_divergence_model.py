import unittest
from jetson.ml_service.main import DivergenceModel


class DivergenceModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = DivergenceModel(baseline_days=1, threshold=2.5)

    def test_score_reflects_recent_spike(self) -> None:
        baseline = []
        timestamp = 1_700_000_000
        for i in range(20):
            baseline.append(
                {
                    "timestamp": timestamp + i * 60,
                    "leds": [
                        {"activity_level": 0.2, "health": "OK"},
                        {"activity_level": 0.1, "health": "OK"},
                    ],
                }
            )
        spike = {
            "timestamp": timestamp + 21 * 60,
            "leds": [
                {"activity_level": 0.9, "health": "ERROR"},
                {"activity_level": 0.8, "health": "ERROR"},
            ],
        }
        history = baseline + [spike]
        result = self.model.score(history)
        self.assertGreaterEqual(result["score"], 2.5)
        self.assertEqual(result["level"], "divergent")
        self.assertIn("active_leds", result["metrics"])

    def test_flat_history_is_normal(self) -> None:
        timestamp = 1_700_000_000
        history = [
            {
                "timestamp": timestamp + i * 60,
                "leds": [
                    {"activity_level": 0.1, "health": "OK"},
                    {"activity_level": 0.1, "health": "OK"},
                ],
            }
            for i in range(10)
        ]
        result = self.model.score(history)
        self.assertEqual(result["level"], "normal")
        self.assertAlmostEqual(result["score"], 0.0, places=3)


if __name__ == "__main__":
    unittest.main()
