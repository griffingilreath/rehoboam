import unittest
from unittest.mock import Mock
from visualizers.generative_eink.channel_daemon import ChannelDaemon, ChannelDaemonConfig, ChannelPublisher, EntityStateEvent
from pathlib import Path

class TestChannelDaemon(unittest.TestCase):
    def test_process_ha_event(self):
        # Mock dependencies
        config = ChannelDaemonConfig(
            entities_path=Path("visualizers/generative_eink/config/entities.example.yaml"),
            channels_path=Path("visualizers/generative_eink/config/channels.example.yaml")
        )
        publisher = Mock(spec=ChannelPublisher)
        
        # Initialize daemon
        daemon = ChannelDaemon(config, publisher)
        
        event_data = {
            "data": {
                "entity_id": "sensor.test",
                "new_state": {
                    "state": "on",
                    "last_changed": "2023-10-26T12:00:00+00:00",
                    "attributes": {"friendly_name": "Test"}
                }
            }
        }
        
        # Mock handle_event to verify it gets called
        daemon.handle_event = Mock()
        
        daemon._process_ha_event(event_data)
        
        daemon.handle_event.assert_called_once()
        args = daemon.handle_event.call_args[0]
        event = args[0]
        self.assertIsInstance(event, EntityStateEvent)
        self.assertEqual(event.entity_id, "sensor.test")
        self.assertEqual(event.state, "on")
        self.assertEqual(event.attributes["friendly_name"], "Test")
