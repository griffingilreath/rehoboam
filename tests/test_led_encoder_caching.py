import unittest
import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from jetson.led_encoder_service.main import LedEncoderService, ServiceConfig

class TestLedEncoderCaching(unittest.TestCase):
    def test_caching(self):
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            state_file = data_dir / "canonical_state.json"
            
            # Mock config
            config = MagicMock(spec=ServiceConfig)
            config.data_dir = data_dir
            config.canonical_path = state_file
            
            service = LedEncoderService(config)
            
            # Initial: No file
            self.assertIsNone(service._load_canonical_state())
            
            # Create file
            state1 = {"leds": [{"index": 0, "health": "OK"}]}
            state_file.write_text(json.dumps(state1), encoding="utf-8")
            
            # Load
            loaded = service._load_canonical_state()
            self.assertEqual(loaded, state1)
            
            # Load again, should be cached (same object identity)
            loaded2 = service._load_canonical_state()
            self.assertIs(loaded, loaded2)
            
            # Update file
            state2 = {"leds": [{"index": 0, "health": "WARNING"}]}
            state_file.write_text(json.dumps(state2), encoding="utf-8")
            
            # Ensure mtime is newer. 
            # In modern linux tmpfs, resolution is high, but to be safe:
            current_mtime = service._last_mtime
            new_mtime = current_mtime + 1.0
            os.utime(state_file, (new_mtime, new_mtime))
            
            # Load
            loaded3 = service._load_canonical_state()
            self.assertEqual(loaded3, state2)
            self.assertIsNot(loaded3, loaded)
            
            # Test corruption (should return cached state)
            state_file.write_text("{invalid_json", encoding="utf-8")
            # Update mtime
            new_mtime += 1.0
            os.utime(state_file, (new_mtime, new_mtime))
            
            loaded4 = service._load_canonical_state()
            self.assertEqual(loaded4, state2) # Should persist state2

if __name__ == "__main__":
    unittest.main()
