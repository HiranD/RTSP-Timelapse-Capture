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


class SchedulerStateOrderingTest(unittest.TestCase):
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

    def test_capture_active_set_before_on_start_capture(self):
        # Symmetric to the stop-path test: lock in that capture_active is already
        # True when on_start_capture fires, so a UI status refresh reads
        # "Capturing" rather than a stale "Active (waiting)".
        seen = {}

        def on_start():
            seen["capture_active"] = scheduler.capture_active

        scheduler = AstroScheduler(
            config_manager=mock.MagicMock(),
            on_start_capture=on_start,
            on_log=lambda *args: None,
        )
        window = mock.MagicMock()
        window.date.strftime.return_value = "20260529"

        scheduler._start_capture_session(window)

        self.assertTrue(
            seen["capture_active"],
            "on_start_capture must observe capture_active already set",
        )
        self.assertTrue(scheduler.capture_active)

    def test_capture_active_set_before_on_start_capture_manual(self):
        # Same contract for the manual-time start path, which is a parallel
        # code path to _start_capture_session.
        seen = {}

        def on_start():
            seen["capture_active"] = scheduler.capture_active

        scheduler = AstroScheduler(
            config_manager=mock.MagicMock(),
            on_start_capture=on_start,
            on_log=lambda *args: None,
        )

        scheduler._start_capture_session_manual("2026-05-29", "22:00", "05:00")

        self.assertTrue(
            seen["capture_active"],
            "on_start_capture must observe capture_active already set (manual path)",
        )
        self.assertTrue(scheduler.capture_active)

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
