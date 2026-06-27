"""
Unit tests for the app-side scheduled-capture timer logic in gui_app.py
(_remote_schedule / _do_scheduled_stop) - where the subtle bugs lived.

These call the methods directly with a mock standing in for the GUI instance, so no Tk
root or capture engine is needed. _run_on_ui is stubbed to run its callable inline.
"""

import sys
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gui_app import RTSPTimelapseGUI  # noqa: E402
from capture_engine import CaptureState  # noqa: E402


def _fake_gui(**overrides):
    """A MagicMock standing in for an RTSPTimelapseGUI instance."""
    g = mock.MagicMock()
    g._run_on_ui.side_effect = lambda fn: fn()  # run inline, no Tk thread
    g.is_capturing = False
    g.start_capture.return_value = (True, None)
    g._start_remote_video.return_value = (True, "ok", 202, "20260625")
    for key, value in overrides.items():
        setattr(g, key, value)
    return g


class RemoteScheduleTests(unittest.TestCase):
    def _schedule(self, g, stop_at, create_video=False):
        return RTSPTimelapseGUI._remote_schedule(g, stop_at, create_video)

    def test_invalid_stop_at(self):
        g = _fake_gui()
        ok, err, _status = self._schedule(g, "not-a-time")
        self.assertFalse(ok)
        self.assertIn("invalid stop_at", err)
        g.start_capture.assert_not_called()
        g._schedule_auto_stop.assert_not_called()

    def test_past_stop_at_rejected(self):
        g = _fake_gui()
        past = (datetime.now() - timedelta(minutes=5)).strftime("%Y%m%d-%H%M%S")
        ok, err, _status = self._schedule(g, past)
        self.assertFalse(ok)
        self.assertIn("past", err)
        g.start_capture.assert_not_called()
        g._schedule_auto_stop.assert_not_called()

    def test_not_capturing_starts_and_uses_session_start(self):
        session_start = datetime(2026, 6, 25, 21, 0, 0)
        g = _fake_gui(is_capturing=False)
        g.capture_engine.session_start_time = session_start
        future = (datetime.now() + timedelta(hours=1)).strftime("%Y%m%d-%H%M%S")
        ok, _err, _status = self._schedule(g, future, create_video=True)
        self.assertTrue(ok)
        g.start_capture.assert_called_once()
        # 'since' is derived from the live session start, not "now".
        g._schedule_auto_stop.assert_called_once()
        self.assertEqual(g._schedule_auto_stop.call_args[0][2],
                         session_start.strftime("%Y%m%d-%H%M%S"))

    def test_already_capturing_uses_existing_session_start(self):
        session_start = datetime(2026, 6, 25, 20, 30, 0)
        g = _fake_gui(is_capturing=True)
        g.capture_engine.session_start_time = session_start
        future = (datetime.now() + timedelta(hours=1)).strftime("%Y%m%d-%H%M%S")
        ok, _err, _status = self._schedule(g, future, create_video=True)
        self.assertTrue(ok)
        g.start_capture.assert_not_called()  # already running - don't restart
        self.assertEqual(g._schedule_auto_stop.call_args[0][2],
                         session_start.strftime("%Y%m%d-%H%M%S"))


class DoScheduledStopTests(unittest.TestCase):
    def _run(self, g, cancel, create_video=True, since="20260625-210000"):
        RTSPTimelapseGUI._do_scheduled_stop(g, cancel, create_video, since)

    def test_bails_when_cancelled(self):
        g = _fake_gui(is_capturing=True)
        cancel = threading.Event()
        cancel.set()
        g._sched_cancel = cancel
        self._run(g, cancel)
        g.stop_capture.assert_not_called()
        g._start_remote_video.assert_not_called()

    def test_bails_when_superseded(self):
        g = _fake_gui(is_capturing=True)
        cancel = threading.Event()
        g._sched_cancel = threading.Event()  # a newer schedule replaced it
        self._run(g, cancel)
        g.stop_capture.assert_not_called()
        g._start_remote_video.assert_not_called()

    def test_fires_stop_and_render(self):
        g = _fake_gui(is_capturing=True)
        cancel = threading.Event()
        g._sched_cancel = cancel
        self._run(g, cancel, create_video=True, since="20260625-210000")
        g.stop_capture.assert_called_once()
        g._start_remote_video.assert_called_once_with(None, "20260625-210000")

    def test_no_render_when_create_video_false(self):
        g = _fake_gui(is_capturing=True)
        cancel = threading.Event()
        g._sched_cancel = cancel
        self._run(g, cancel, create_video=False)
        g.stop_capture.assert_called_once()
        g._start_remote_video.assert_not_called()


class RemoteStartCaptureTests(unittest.TestCase):
    """POST /capture/start must not replace/orphan a running engine (idempotent)."""

    def test_start_while_idle_starts_capture(self):
        g = _fake_gui(is_capturing=False)
        ok, _err, _status = RTSPTimelapseGUI._remote_start_capture(g)
        self.assertTrue(ok)
        g.start_capture.assert_called_once()

    def test_start_while_capturing_is_idempotent_noop(self):
        g = _fake_gui(is_capturing=True)
        ok, _err, _status = RTSPTimelapseGUI._remote_start_capture(g)
        self.assertTrue(ok)
        # Already capturing: don't call start_capture (which would orphan the engine).
        g.start_capture.assert_not_called()


class NaturalStopTests(unittest.TestCase):
    """A natural/automatic stop (disconnect, error, end_dt) must cancel a pending auto-stop."""

    def test_natural_stop_cancels_scheduled_timer(self):
        g = _fake_gui(is_capturing=True)
        RTSPTimelapseGUI.update_status_from_engine(
            g, CaptureState.ERROR, {"frame_count": 3, "uptime_seconds": 42})
        g._cancel_scheduled_stop.assert_called_once()
        self.assertFalse(g.is_capturing)


if __name__ == "__main__":
    unittest.main(verbosity=2)
