import unittest
from jetson.common.led_codes import HealthCode, ActivityType

class TestLEDCodes(unittest.TestCase):
    def test_health_codes_match_firmware(self):
        # Firmware definitions:
        # 0: OFF
        # 1: OK
        # 2: WARN
        # 3: ERR
        # 4: UNK
        
        self.assertEqual(HealthCode.OFF.value, 0)
        self.assertEqual(HealthCode.OK.value, 1)
        self.assertEqual(HealthCode.WARNING.value, 2)
        self.assertEqual(HealthCode.ERROR.value, 3)
        self.assertEqual(HealthCode.UNKNOWN.value, 4)

    def test_activity_codes_match_firmware(self):
        # Firmware definitions:
        # 2: Blind
        # 3: DNS
        
        self.assertEqual(ActivityType.BLIND_MOVE.value, 2)
        self.assertEqual(ActivityType.DNS_QUERIES.value, 3)

if __name__ == "__main__":
    unittest.main()
