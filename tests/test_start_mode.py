"""
Unit tests for the Capture Window "Start: At time / Now" mode.

"Now" is implemented by transiently setting the engine's start_time to the
current minute (resolve_start_time) so capture begins immediately while the
End Time still bounds the session. These tests verify the pure resolver and,
against a real CaptureEngine, that a start_time equal to "now" starts without
waiting and computes a future end for both same-day and overnight windows.
No GUI, camera, or network required.
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config_manager import ConfigManager  # noqa: E402
from capture_engine import CaptureEngine  # noqa: E402
from gui_app import resolve_start_time  # noqa: E402


class ResolveStartTimeTests(unittest.TestCase):
    def test_now_returns_current_minute(self):
        now = datetime(2026, 7, 24, 20, 15, 42)
        self.assertEqual(resolve_start_time("now", now, "22:40"), "20:15")

    def test_now_is_not_in_the_future(self):
        # Flooring to the minute guarantees start <= now, so the engine never waits.
        now = datetime(2026, 7, 24, 20, 15, 59)
        resolved = resolve_start_time("now", now, "22:40")
        h, m = map(int, resolved.split(":"))
        self.assertLessEqual((h, m), (now.hour, now.minute))

    def test_at_time_returns_configured_value(self):
        now = datetime(2026, 7, 24, 20, 15, 0)
        self.assertEqual(resolve_start_time("at_time", now, "22:40"), "22:40")

    def test_unknown_mode_falls_through_to_configured(self):
        now = datetime(2026, 7, 24, 20, 15, 0)
        self.assertEqual(resolve_start_time("", now, "22:40"), "22:40")


def _engine(start, end):
    cfg = ConfigManager().to_dict()
    cfg["schedule"]["start_time"] = start
    cfg["schedule"]["end_time"] = end
    return CaptureEngine(cfg)


class StartNowEngineBehaviorTests(unittest.TestCase):
    """The transient 'now' start_time must start immediately and bound by End Time."""

    def setUp(self):
        # Use the actual current minute, exactly as the GUI would produce it.
        self.now = datetime.now()
        self.now_str = self.now.strftime("%H:%M")

    def test_starts_immediately(self):
        # Same-minute start means _wait_for_start_time returns at once (no wait).
        eng = _engine(start=self.now_str, end="23:59")
        self.assertTrue(eng._wait_for_start_time())

    def test_end_is_in_the_future_same_day(self):
        # End later today than now -> ends today, strictly after now.
        later = (self.now + timedelta(hours=2)).strftime("%H:%M")
        eng = _engine(start=self.now_str, end=later)
        self.assertGreater(eng._calculate_end_time(), datetime.now())

    def test_end_is_in_the_future_overnight(self):
        # End earlier in the day than now (overnight) -> next occurrence is tomorrow.
        earlier = (self.now - timedelta(hours=2)).strftime("%H:%M")
        eng = _engine(start=self.now_str, end=earlier)
        end_dt = eng._calculate_end_time()
        self.assertGreater(end_dt, datetime.now())
        # And it should be within the next 24h (tomorrow's occurrence, not later).
        self.assertLess(end_dt, datetime.now() + timedelta(hours=24))


if __name__ == "__main__":
    unittest.main(verbosity=2)
