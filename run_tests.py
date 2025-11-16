import unittest

try:
    from colorama import init, Fore, Style  # type: ignore
except Exception:  # pragma: no cover - fallback if colorama not installed
    class Dummy:
        RESET_ALL = ""

    class ForeDummy(Dummy):
        GREEN = ""
        RED = ""
        MAGENTA = ""
        YELLOW = ""

    init = lambda autoreset=True: None  # noqa: E731
    Fore = ForeDummy()  # type: ignore
    Style = Dummy()  # type: ignore


# Initialize ANSI color support on Windows / other terminals
init(autoreset=True)


class ColorTextResult(unittest.TextTestResult):
    """Custom TextTestResult with colored, explicit per-test output."""

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        unittest.TestResult.addSuccess(self, test)
        self.stream.writeln(f"{Fore.GREEN}✓ {test}{Style.RESET_ALL}")

    def addFailure(self, test: unittest.case.TestCase, err) -> None:
        unittest.TestResult.addFailure(self, test, err)
        self.stream.writeln(f"{Fore.RED}✗ {test} (FAIL){Style.RESET_ALL}")
        if self.showAll:
            self.stream.writeln(self._exc_info_to_string(err, test))

    def addError(self, test: unittest.case.TestCase, err) -> None:
        unittest.TestResult.addError(self, test, err)
        self.stream.writeln(f"{Fore.MAGENTA}! {test} (ERROR){Style.RESET_ALL}")
        if self.showAll:
            self.stream.writeln(self._exc_info_to_string(err, test))

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        unittest.TestResult.addSkip(self, test, reason)
        self.stream.writeln(f"{Fore.YELLOW}- {test} (skipped: {reason}){Style.RESET_ALL}")


def main() -> None:
    loader = unittest.TestLoader()
    suite = loader.discover("tests")
    runner = unittest.TextTestRunner(verbosity=2, resultclass=ColorTextResult)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()


