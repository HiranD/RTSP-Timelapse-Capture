"""
Unit tests for manual/remote session recording in gui_app.

Only the scheduler used to write capture history; manual and NINA/remote
sessions vanished from the calendar once their snapshots were deleted. The GUI
now records its own (non-scheduled) sessions on both stop paths - stop_capture
and the natural-stop branch of update_status_from_engine - with a guard so
exactly one record fires per session.

Sessions are dated by their first frame, not by the Start click: in "At time"
start mode the engine waits for the window, and a morning click for an evening
window would otherwise land on the previous night via the rollover rule.

A manual session that saved no frames is not recorded at all (a Start/Stop while
testing, with the user watching); an empty remote session is, since it ran
unattended and the record is the only trace that the night failed.

GUI methods are exercised unbound against mock.MagicMock() stand-ins (the
test_scheduler_autovideo.py pattern), so no Tk root or camera is needed.
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from capture_engine import CaptureState, effective_date  # noqa: E402
from gui_app import RTSPTimelapseGUI  # noqa: E402

SESSION_START = datetime(2026, 9, 5, 20, 41, 0)


def _gui(source="manual", start=SESSION_START, rollover=12, frames=812,
         first_frame=None):
    g = mock.MagicMock()
    g._session_source = source
    g.session_start_time = start       # the Start click
    g._first_frame_time = first_frame  # None = no frame ever arrived
    g.config_manager.schedule.folder_rollover_hour = rollover
    g.total_captures = frames
    return g


class RecordOwnSessionTests(unittest.TestCase):
    def _record(self, g):
        with mock.patch("gui_app.get_capture_history") as gch:
            RTSPTimelapseGUI._record_own_session(g)
        return gch.return_value.record_session

    def test_manual_session_recorded_with_source(self):
        g = _gui(source="manual")
        record = self._record(g)
        record.assert_called_once()
        kwargs = record.call_args.kwargs
        self.assertEqual(kwargs["date"], "20260905")
        self.assertEqual(kwargs["start_time"], SESSION_START)
        self.assertEqual(kwargs["image_count"], 812)
        self.assertEqual(kwargs["source"], "manual")
        self.assertFalse(kwargs["video_created"])
        g.scheduling_panel.refresh_calendar.assert_called_once()

    def test_post_midnight_start_lands_on_previous_day(self):
        """A 01:30 start belongs to the previous night - same effective-date
        rule the snapshot folders follow."""
        g = _gui(source="remote", start=datetime(2026, 9, 6, 1, 30, 0))
        record = self._record(g)
        self.assertEqual(record.call_args.kwargs["date"], "20260905")
        self.assertEqual(record.call_args.kwargs["source"], "remote")

    def test_session_is_dated_by_its_first_frame_not_the_click(self):
        """"At time" start mode: Start clicked in the morning, frames from the
        evening window. Dated by the click, the rollover rule would file the
        night under the previous date and show 09:30 as the start."""
        click = datetime(2026, 9, 5, 9, 30, 0)
        first_frame = datetime(2026, 9, 5, 21, 0, 0)
        # The trap this guards against: the click alone maps to the 4th.
        self.assertEqual(effective_date(click, 12).strftime("%Y%m%d"), "20260904")

        record = self._record(_gui(start=click, first_frame=first_frame))
        kwargs = record.call_args.kwargs
        self.assertEqual(kwargs["date"], "20260905")
        self.assertEqual(kwargs["start_time"], first_frame)

    def test_no_frames_falls_back_to_the_click_time(self):
        # Remote: an empty manual session isn't recorded at all (next test).
        record = self._record(_gui(source="remote", start=SESSION_START,
                                   first_frame=None, frames=0))
        self.assertEqual(record.call_args.kwargs["start_time"], SESSION_START)
        self.assertEqual(record.call_args.kwargs["image_count"], 0)

    def test_empty_manual_session_is_not_recorded(self):
        """Start then Stop while testing, with the user watching the log: a
        "0 frames (failed)" hover line would only be clutter."""
        self._record(_gui(source="manual", frames=0)).assert_not_called()

    def test_empty_remote_session_is_still_recorded(self):
        """Unattended: NINA started capture and nothing came - worth a trace."""
        record = self._record(_gui(source="remote", frames=0))
        self.assertEqual(record.call_args.kwargs["source"], "remote")
        self.assertEqual(record.call_args.kwargs["image_count"], 0)

    def test_scheduled_session_is_skipped(self):
        """The scheduler's own on_session_complete path records those -
        recording here too would double-count the night."""
        g = _gui(source="scheduled")
        self._record(g).assert_not_called()

    def test_never_started_session_is_skipped(self):
        self._record(_gui(source=None)).assert_not_called()
        self._record(_gui(start=None)).assert_not_called()

    def test_record_failure_is_logged_not_raised(self):
        g = _gui()
        with mock.patch("gui_app.get_capture_history",
                        side_effect=OSError("disk full")):
            RTSPTimelapseGUI._record_own_session(g)  # must not raise
        level = g.log_message.call_args.args[0]
        self.assertEqual(level, "WARNING")


class StopPathGuardTests(unittest.TestCase):
    """Exactly one record per session, whichever stop path runs."""

    def test_stop_capture_records_when_capturing(self):
        g = mock.MagicMock()
        g.is_capturing = True
        RTSPTimelapseGUI.stop_capture(g)
        g._record_own_session.assert_called_once()
        self.assertFalse(g.is_capturing)

    def test_stop_capture_skips_when_already_stopped(self):
        """After the natural-stop branch ran, a later stop_capture (e.g. the
        user clicking Stop on an already-ended session) must not re-record."""
        g = mock.MagicMock()
        g.is_capturing = False
        RTSPTimelapseGUI.stop_capture(g)
        g._record_own_session.assert_not_called()

    def test_natural_stop_records_when_capturing(self):
        g = mock.MagicMock()
        g.is_capturing = True
        g._sched_pending = None
        RTSPTimelapseGUI.update_status_from_engine(g, CaptureState.STOPPED, {})
        g._record_own_session.assert_called_once()
        self.assertFalse(g.is_capturing)

    def test_natural_stop_skips_after_stop_capture(self):
        """stop_capture already flipped is_capturing before the engine's
        STOPPED callback arrives via after(0, ...) - the branch must not fire
        a second record."""
        g = mock.MagicMock()
        g.is_capturing = False
        RTSPTimelapseGUI.update_status_from_engine(g, CaptureState.STOPPED, {})
        g._record_own_session.assert_not_called()


class FirstFrameTimeTests(unittest.TestCase):
    """on_frame_captured stamps the first frame's arrival exactly once."""

    def test_first_frame_time_is_set_once(self):
        g = mock.MagicMock()
        g.total_captures = 0
        g._first_frame_time = None
        RTSPTimelapseGUI.on_frame_captured(g, object())
        first = g._first_frame_time
        self.assertIsInstance(first, datetime)
        RTSPTimelapseGUI.on_frame_captured(g, object())
        self.assertIs(g._first_frame_time, first)
        self.assertEqual(g.total_captures, 2)


if __name__ == "__main__":
    unittest.main()
