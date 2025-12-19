import unittest
from unittest.mock import MagicMock, patch
import subprocess
from epaper.backends.usb_backend import USBBackend
from PIL import Image

class TestUSBBackendErrorHandling(unittest.TestCase):
    @patch("epaper.backends.usb_backend.shutil.which")
    @patch("epaper.backends.usb_backend.subprocess.Popen")
    @patch("epaper.backends.usb_backend.Path")
    def test_subprocess_timeout(self, mock_path, mock_popen, mock_which):
        # Setup mocks
        mock_which.return_value = "/bin/it8951usb"
        mock_path.return_value.exists.return_value = True
        
        process_mock = MagicMock()
        process_mock.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="cmd", timeout=10),
            (b"", b"")
        ]
        process_mock.stdin = MagicMock()
        mock_popen.return_value = process_mock

        backend = USBBackend()
        backend.open()
        
        img = Image.new("L", (100, 100))
        
        with self.assertRaisesRegex(RuntimeError, "USB backend timed out"):
            backend.draw_full(img)
            
        process_mock.kill.assert_called_once()
        # Verify cleanup call happened
        self.assertEqual(process_mock.communicate.call_count, 2)

    @patch("epaper.backends.usb_backend.shutil.which")
    @patch("epaper.backends.usb_backend.subprocess.Popen")
    @patch("epaper.backends.usb_backend.Path")
    def test_subprocess_error_code(self, mock_path, mock_popen, mock_which):
        # Setup mocks
        mock_which.return_value = "/bin/it8951usb"
        mock_path.return_value.exists.return_value = True
        
        process_mock = MagicMock()
        # communicate returns (stdout, stderr)
        process_mock.communicate.return_value = (b"", b"Some error occurred")
        process_mock.returncode = 1
        process_mock.stdin = MagicMock()
        mock_popen.return_value = process_mock

        backend = USBBackend()
        backend.open()
        
        img = Image.new("L", (100, 100))
        
        with self.assertRaisesRegex(RuntimeError, "USB backend failed.*Some error occurred"):
            backend.draw_full(img)

if __name__ == "__main__":
    unittest.main()
