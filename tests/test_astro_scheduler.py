"""
Unit tests for src/astro_scheduler.py

Focus: the status-label correctness contract — `capture_active` must be cleared
BEFORE `on_stop_capture` fires, so the UI status refresh reads the post-stop
state instead of a stale "Capturing".
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from astro_scheduler import AstroScheduler  # noqa: E402


class StopCaptureSessionOrderingTest(unittest.TestCase):
    def test_capture_active_cleared_before_on_stop_capture(self):
        seen = {}

        def on_stop():
            # Capture the flag value the UI would read at notification time.
            seen["capture_active"] = scheduler.capture_active

        scheduler = AstroScheduler(
            config_manager=mock.MagicMock(),
            on_stop_capture=on_stop,
            on_log=lambda *args: None,
        )
        scheduler.capture_active = True
        scheduler.current_session_date = "20260529"

        scheduler._stop_capture_session()

        self.assertFalse(
            seen["capture_active"],
            "on_stop_capture must observe capture_active already cleared",
        )
        self.assertFalse(scheduler.capture_active)

    def test_session_complete_still_fires_after_stop(self):
        completed = []
        scheduler = AstroScheduler(
            config_manager=mock.MagicMock(),
            on_stop_capture=lambda: None,
            on_session_complete=completed.append,
            on_log=lambda *args: None,
        )
        scheduler.capture_active = True
        scheduler.current_session_date = "20260529"

        scheduler._stop_capture_session()

        self.assertEqual(completed, ["20260529"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
