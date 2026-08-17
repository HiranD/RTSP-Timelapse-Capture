"""
Unit tests for the session-aware nightly auto-video wiring:
SchedulingPanel._on_session_complete / _maybe_autocreate_video passing the
session start through to gui_app._scheduler_create_video.

The subtle bug these pin down: _on_session_complete clears session_start_time
before the after() callback fires, so the start must be captured first and
bound into the lambda - otherwise the render always falls back to whole-folder.

Same approach as test_scheduled_capture.py: MagicMocks stand in for the panel
and GUI instances, so no Tk root, scheduler, or capture engine is needed.
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from scheduling_panel import SchedulingPanel  # noqa: E402
from gui_app import RTSPTimelapseGUI  # noqa: E402

SESSION_START = datetime(2026, 7, 25, 20, 0, 0)


class OnSessionCompleteTests(unittest.TestCase):
    def test_session_start_captured_before_clear(self):
        """The field is cleared as before, but the lambda must hold the original."""
        p = mock.MagicMock()
        p.session_start_time = SESSION_START
        SchedulingPanel._on_session_complete(p, "20260725")

        self.assertIsNone(p.session_start_time, "the consume-once clear must survive")
        delay, callback = p.after.call_args[0]
        self.assertEqual(delay, 0)
        callback()
        p._maybe_autocreate_video.assert_called_once_with("20260725", SESSION_START)

    def test_history_still_recorded_before_clear(self):
        p = mock.MagicMock()
        p.session_start_time = SESSION_START
        SchedulingPanel._on_session_complete(p, "20260725")
        p._record_capture_session.assert_called_once_with("20260725")


class MaybeAutocreateVideoTests(unittest.TestCase):
    def _panel(self, auto_video=True):
        p = mock.MagicMock()
        p._widget_alive.return_value = True
        p.auto_video_var.get.return_value = auto_video
        return p

    def test_passes_start_to_callback(self):
        p = self._panel()
        SchedulingPanel._maybe_autocreate_video(p, "20260725", SESSION_START)
        p.create_video_callback.assert_called_once_with("20260725", SESSION_START)

    def test_no_callback_when_auto_video_off(self):
        p = self._panel(auto_video=False)
        SchedulingPanel._maybe_autocreate_video(p, "20260725", SESSION_START)
        p.create_video_callback.assert_not_called()


class SchedulerCreateVideoTests(unittest.TestCase):
    """The gui_app adapter: session start known -> the same session-aware path
    as the scheduled stop; unknown -> the old whole-folder render."""

    def test_with_start_uses_session_aware_path(self):
        g = mock.MagicMock()
        g._start_remote_video.return_value = (True, "ok", 202, "20260725")
        RTSPTimelapseGUI._scheduler_create_video(g, "20260725", SESSION_START)
        g._start_remote_video.assert_called_once_with(None, "20260725-200000")
        g._auto_create_video_for_date.assert_not_called()

    def test_without_start_falls_back_to_whole_folder(self):
        g = mock.MagicMock()
        RTSPTimelapseGUI._scheduler_create_video(g, "20260725", None)
        g._auto_create_video_for_date.assert_called_once_with("20260725")
        g._start_remote_video.assert_not_called()

    def test_failure_is_logged_not_raised(self):
        g = mock.MagicMock()
        g._start_remote_video.return_value = (False, "no capture folders found", 404, None)
        RTSPTimelapseGUI._scheduler_create_video(g, "20260725", SESSION_START)
        level, message = g.log_message.call_args[0]
        self.assertEqual(level, "ERROR")
        self.assertIn("no capture folders found", message)


if __name__ == "__main__":
    unittest.main()
