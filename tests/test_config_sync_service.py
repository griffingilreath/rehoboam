import json
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

import yaml

from jetson.common.service_runner import RunnerOverrides
from jetson.config_sync_service.main import ConfigSyncService, load_service_config


class FakeHAClient:
    def __init__(self, values):
        self._values = values

    def read_entity_state(self, entity_id: str) -> str:
        return self._values.get(entity_id, f"value-for-{entity_id}")
        
    async def read_entity_state_async(self, session, entity_id: str) -> str:
        return self._values.get(entity_id, f"value-for-{entity_id}")


class ConfigSyncServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_config_sync_writes_led_config_async(self):
        data_dir = Path(self._tmpdir())
        cfg = {
            "data_dir": str(data_dir),
            "poll_interval_seconds": 1,
            "led_count": 1,
            "home_assistant": {"base_url": "http://ha.local", "token": "abc"},
            "templates": {
                "name": "device_{index}_name",
                "ip": "device_{index}_ip",
                "type": "device_{index}_type",
                "ha_availability_entity": "binary_sensor.device_{index}",
                "extra_fields": {"event_entities": "sensor.device_{index}_events"},
            },
        }
        cfg_path = data_dir / "config.yaml"
        cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

        config = load_service_config(cfg_path, RunnerOverrides(data_dir=data_dir))
        service = ConfigSyncService(config)
        
        # Mock the client
        service._client = FakeHAClient(
            {
                "device_0_name": "Rack Switch",
                "device_0_ip": "192.168.1.10",
                "device_0_type": "network",
                "binary_sensor.device_0": "on",
                "sensor.device_0_events": "binary_sensor.motion",
            }
        )

        mock_session = MagicMock()
        await service.sync_once_async(mock_session)

        payload = json.loads((data_dir / "led_config.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["leds"][0]["name"], "Rack Switch")
        self.assertEqual(payload["leds"][0]["ip"], "192.168.1.10")

    def _tmpdir(self) -> str:
        from tempfile import TemporaryDirectory

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


if __name__ == "__main__":
    unittest.main()
