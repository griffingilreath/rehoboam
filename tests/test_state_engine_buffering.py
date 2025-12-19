import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from jetson.state_engine_service.main import StateEngineService, ServiceConfig

class TestStateEngineBuffering(unittest.TestCase):
    def test_buffering(self):
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            history_file = data_dir / "history.json"
            
            config = MagicMock(spec=ServiceConfig)
            config.data_dir = data_dir
            config.history_path = history_file
            config.history_enabled = True
            config.history_flush_interval_seconds = 60.0
            config.history_max_entries = 100
            config.history_retention_seconds = 3600
            
            service = StateEngineService(config)
            
            # Record one entry
            entry1 = {"timestamp": 100, "data": 1}
            service._record_history(entry1)
            
            # Buffer should have 1 item
            self.assertEqual(len(service._history_buffer), 1)
            # File should not exist
            self.assertFalse(history_file.exists())
            
            # Record another
            entry2 = {"timestamp": 101, "data": 2}
            service._record_history(entry2)
            self.assertEqual(len(service._history_buffer), 2)
            self.assertFalse(history_file.exists())
            
            # Force flush
            service._flush_history()
            
            self.assertEqual(len(service._history_buffer), 0)
            self.assertTrue(history_file.exists())
            
            content = json.loads(history_file.read_text())
            self.assertEqual(len(content["entries"]), 2)
            self.assertEqual(content["entries"][0]["data"], 1)
            self.assertEqual(content["entries"][1]["data"], 2)
            
            # Test auto-flush on buffer size
            # Add 50 items. The limit is 50.
            # The check is: if len >= 50: flush.
            # So when we add the 50th item (len becomes 1), wait...
            # Buffer accumulates. 
            # We add 1. Len 1.
            # ...
            # We add 50. Len 50. Flush.
            
            for i in range(50):
                service._record_history({"timestamp": 200+i, "data": i})
            
            self.assertEqual(len(service._history_buffer), 0)
            content = json.loads(history_file.read_text())
            # 2 previous + 50 new = 52
            self.assertEqual(len(content["entries"]), 52)

if __name__ == "__main__":
    unittest.main()
