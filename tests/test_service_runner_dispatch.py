import unittest
import inspect
from unittest.mock import MagicMock
from jetson.common.service_runner import _dispatch_service_run

class TestServiceDispatch(unittest.TestCase):
    def test_run_accepts_run_once(self):
        service = MagicMock()
        # Mock run method signature to accept run_once
        def run(run_once=False):
            pass
        service.run = MagicMock(side_effect=run)
        service.run.__signature__ = inspect.signature(run)
        
        _dispatch_service_run(service, run_once=True)
        service.run.assert_called_with(run_once=True)

    def test_run_does_not_accept_run_once_fallback_to_run_once(self):
        service = MagicMock()
        # Mock run method to NOT accept arguments
        def run():
            pass
        service.run = MagicMock(side_effect=run)
        service.run.__signature__ = inspect.signature(run)
        # Mock run_once method
        service.run_once = MagicMock()
        
        _dispatch_service_run(service, run_once=True)
        service.run_once.assert_called_once()
        service.run.assert_not_called()

    def test_run_does_not_accept_run_once_fallback_to_run(self):
        service = MagicMock()
        # Mock run method to NOT accept arguments
        def run():
            pass
        service.run = MagicMock(side_effect=run)
        service.run.__signature__ = inspect.signature(run)
        # Ensure no run_once method
        del service.run_once
        
        _dispatch_service_run(service, run_once=True)
        service.run.assert_called_once() # Called without arguments

    def test_type_error_propagation(self):
        # This is the key test for the fix.
        # If run accepts run_once but raises TypeError internally, it should propagate.
        service = MagicMock()
        def run(run_once=False):
            raise TypeError("Internal type error")
        service.run = MagicMock(side_effect=run)
        service.run.__signature__ = inspect.signature(run)
        
        with self.assertRaisesRegex(TypeError, "Internal type error"):
            _dispatch_service_run(service, run_once=True)

if __name__ == "__main__":
    unittest.main()
