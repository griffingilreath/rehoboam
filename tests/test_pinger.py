import unittest
from jetson.collector_service.main import Pinger, PingConfig

class TestPinger(unittest.TestCase):
    def test_parse_rtt_linux(self):
        output = "rtt min/avg/max/mdev = 0.045/0.055/0.065/0.000 ms"
        rtt = Pinger._parse_rtt_ms(output)
        self.assertEqual(rtt, 0.055)

    def test_parse_rtt_windows(self):
        output = """
Pinging 1.1.1.1 with 32 bytes of data:
Reply from 1.1.1.1: bytes=32 time=2ms TTL=50
Reply from 1.1.1.1: bytes=32 time=2ms TTL=50

Ping statistics for 1.1.1.1:
    Packets: Sent = 2, Received = 2, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 2ms, Maximum = 2ms, Average = 2ms
"""
        rtt = Pinger._parse_rtt_ms(output)
        self.assertEqual(rtt, 2.0)

    def test_parse_rtt_invalid(self):
        output = "PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data."
        rtt = Pinger._parse_rtt_ms(output)
        self.assertIsNone(rtt)

if __name__ == '__main__':
    unittest.main()
