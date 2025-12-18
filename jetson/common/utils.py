"""Shared utilities for service loops and timing."""
from __future__ import annotations

import time


def wait_for_next_cycle(start_time: float, interval_seconds: float) -> None:
    """Sleep for the remainder of the interval."""
    elapsed = time.monotonic() - start_time
    sleep_for = max(0.0, interval_seconds - elapsed)
    if sleep_for > 0:
        time.sleep(sleep_for)
