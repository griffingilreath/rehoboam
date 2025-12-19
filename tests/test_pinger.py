import unittest
from jetson.collector_service.main import Pinger

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

    def test_linux_iputils_full(self):
        output = """
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=115 time=13.4 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 13.425/13.425/13.425/0.000 ms
"""
        self.assertAlmostEqual(Pinger._parse_rtt_ms(output), 13.425)

    def test_linux_busybox(self):
        output = """
PING 8.8.8.8 (8.8.8.8): 56 data bytes
64 bytes from 8.8.8.8: seq=0 ttl=115 time=13.4 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 packets received, 0% packet loss
round-trip min/avg/max = 13.425/13.425/13.425 ms
"""
        self.assertAlmostEqual(Pinger._parse_rtt_ms(output), 13.425)

    def test_mac_bsd(self):
        output = """
PING 8.8.8.8 (8.8.8.8): 56 data bytes
64 bytes from 8.8.8.8: icmp_seq=0 ttl=115 time=13.425 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 13.425/13.425/13.425/0.000 ms
"""
        self.assertAlmostEqual(Pinger._parse_rtt_ms(output), 13.425)

if __name__ == '__main__':
    unittest.main()
