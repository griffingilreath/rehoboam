import json
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from jetson.collector_service.main import (
    EventConfig,
    CollectorService,
    HomeAssistantConfig,
    PiHoleConfig,
    PingConfig,
    ServiceConfig,
)


class FakeBuffer:
    def snapshot(self):
        return [{"entity_id": "binary_sensor.test", "timestamp": 0}]

    def count_for_entities(self, entities):
        return 1


class FakeWriter:
    def append_many(self, events):
        self.events = events


class CollectorServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_collect_once_async_writes_raw_state(self):
        data_dir = Path(self._tmpdir())
        led_config = {
            "leds": [
                {"index": 0, "name": "Device A", "event_entities": ["binary_sensor.test"]},
            ]
        }
        (data_dir / "led_config.json").write_text(json.dumps(led_config), encoding="utf-8")

        config = ServiceConfig(
            data_dir=data_dir,
            led_config_filename="led_config.json",
            raw_state_filename="raw_state.json",
            events_log_filename="events.json",
            poll_interval_seconds=1.0,
            event_buffer_seconds=5.0,
            context_entities=[],
            home_assistant=HomeAssistantConfig(base_url="http://ha.local", token="token"),
            pihole=PiHoleConfig(),
            ping=PingConfig(),
            events=EventConfig(),
        )
        service = CollectorService(config)
        service._event_buffer = FakeBuffer()  # type: ignore[attr-defined]
        service._event_log_writer = FakeWriter()  # type: ignore[attr-defined]
        service._load_led_config = lambda: led_config  # type: ignore[attr-defined]
        
        # Mock the async methods
        service._collect_device_state_async = AsyncMock(return_value={"reachable": True})
        service._build_context_snapshot_async = AsyncMock(return_value={"flags": {"occupied": True}})

        # Mock session
        mock_session = MagicMock()

        await service.collect_once_async(mock_session)

        payload = json.loads((data_dir / "raw_state.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertTrue(payload["devices"]["Device A"]["reachable"])
        
        # Verify mocks were called
        service._collect_device_state_async.assert_called_once()
        service._build_context_snapshot_async.assert_called_once()

    def _tmpdir(self) -> str:
        from tempfile import TemporaryDirectory

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


if __name__ == "__main__":
    unittest.main()
