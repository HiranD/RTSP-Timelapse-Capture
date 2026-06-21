"""
Unit tests for the CaptureEngine "ignore_window" (remote-control) mode.

Remote/NINA-triggered captures must start immediately and run until explicitly
stopped, ignoring the Capture-tab schedule window. These tests verify the
short-circuit in _wait_for_start_time() without a real camera or any waiting.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config_manager import ConfigManager  # noqa: E402
from capture_engine import CaptureEngine  # noqa: E402


def _engine(ignore_window, start="23:59", end="23:58"):
    cfg = ConfigManager().to_dict()
    cfg["schedule"]["start_time"] = start
    cfg["schedule"]["end_time"] = end
    if ignore_window:
        cfg["schedule"]["ignore_window"] = True
    return CaptureEngine(cfg)


class IgnoreWindowTests(unittest.TestCase):
    def test_ignore_window_starts_immediately(self):
        # With ignore_window set, the engine proceeds regardless of start_time
        # (a future "23:59" start would otherwise force a wait).
        eng = _engine(ignore_window=True, start="23:59", end="23:58")
        self.assertTrue(eng._wait_for_start_time())

    def test_ignore_window_does_not_consult_stop_event(self):
        # Even with stop_event already set, the ignore path returns True at once,
        # proving it never enters the (interruptible) wait branch.
        eng = _engine(ignore_window=True, start="00:00", end="23:59")
        eng.stop_event.set()
        self.assertTrue(eng._wait_for_start_time())

    def test_flag_absent_by_default(self):
        # A normal config has no ignore_window key, so the scheduled path applies.
        cfg = ConfigManager().to_dict()
        self.assertNotIn("ignore_window", cfg["schedule"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
