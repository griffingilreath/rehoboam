import unittest
from pathlib import Path

from epaper.service.main import EpaperService, ServiceConfig


class EpaperServiceTest(unittest.TestCase):
    def test_unknown_scene_exits_nonzero(self) -> None:
        tmpdir = Path(self._tmpdir())
        config = ServiceConfig(
            data_dir=tmpdir,
            backend="fake",
            backend_config={"out_dir": tmpdir / "frames"},
            scene="this_scene_does_not_exist",
            log_level="INFO",
        )
        service = EpaperService(config)

        with self.assertRaises(SystemExit) as cm:
            service.run()

        # The important behavior: do not exit successfully (code 0/None).
        self.assertIsNotNone(cm.exception.code)
        self.assertNotEqual(cm.exception.code, 0)

    def _tmpdir(self) -> str:
        from tempfile import TemporaryDirectory

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


if __name__ == "__main__":
    unittest.main()
