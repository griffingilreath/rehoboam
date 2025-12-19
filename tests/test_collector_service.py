import json
import unittest
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


class PingParsingTest(unittest.TestCase):
    def test_linux_iputils(self):
        from jetson.collector_service.main import Pinger
        output = """
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=115 time=13.4 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 13.425/13.425/13.425/0.000 ms
"""
        self.assertAlmostEqual(Pinger._parse_rtt_ms(output), 13.425)

    def test_linux_busybox(self):
        from jetson.collector_service.main import Pinger
        output = """
PING 8.8.8.8 (8.8.8.8): 56 data bytes
64 bytes from 8.8.8.8: seq=0 ttl=115 time=13.4 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 packets received, 0% packet loss
round-trip min/avg/max = 13.425/13.425/13.425 ms
"""
        self.assertAlmostEqual(Pinger._parse_rtt_ms(output), 13.425)

    def test_windows(self):
        from jetson.collector_service.main import Pinger
        output = """
Pinging 8.8.8.8 with 32 bytes of data:
Reply from 8.8.8.8: bytes=32 time=13ms TTL=115

Ping statistics for 8.8.8.8:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 13ms, Maximum = 13ms, Average = 13ms
"""
        self.assertEqual(Pinger._parse_rtt_ms(output), 13.0)

    def test_mac_bsd(self):
        from jetson.collector_service.main import Pinger
        output = """
PING 8.8.8.8 (8.8.8.8): 56 data bytes
64 bytes from 8.8.8.8: icmp_seq=0 ttl=115 time=13.425 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 13.425/13.425/13.425/0.000 ms
"""
        self.assertAlmostEqual(Pinger._parse_rtt_ms(output), 13.425)

    def test_no_output(self):
        from jetson.collector_service.main import Pinger
        self.assertIsNone(Pinger._parse_rtt_ms(""))

    def test_partial_output(self):
        from jetson.collector_service.main import Pinger
        output = "PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data."
        self.assertIsNone(Pinger._parse_rtt_ms(output))


if __name__ == "__main__":
    unittest.main()
