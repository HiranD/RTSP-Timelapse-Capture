"""
Unit tests for the calendar's capture-source coloring and hover text.

Widget methods are exercised unbound against a MagicMock stand-in (the
test_scheduler_autovideo.py pattern) so no Tk root is needed; the tooltip text
builder is a plain module function.
"""

import calendar
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from capture_history import CaptureHistoryManager, CaptureSession  # noqa: E402
from calendar_widget import TwoMonthCalendar, build_day_tooltip_text  # noqa: E402

DAY = date(2026, 9, 5)
DATE = "20260905"


def _session(source="scheduled", images=800, video=False, status="completed",
             start="2026-09-05T20:41:00", end="2026-09-06T05:12:00"):
    return CaptureSession(date=DATE, start_time=start, end_time=end,
                          image_count=images, video_created=video,
                          status=status, source=source)


class CaptureKindTests(unittest.TestCase):
    """Which color bucket a past day lands in."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.history = CaptureHistoryManager(config_dir=Path(self._tmp.name))
        self.p = mock.MagicMock()
        self.p.capture_history = self.history
        self.p._folder_has_images.return_value = False

    def _kind(self):
        return TwoMonthCalendar._get_capture_kind(self.p, DAY)

    def test_scheduled_session_is_captured(self):
        self.history.sessions[DATE] = [_session(source="scheduled")]
        self.assertEqual(self._kind(), "captured")

    def test_manual_only_is_captured_other(self):
        self.history.sessions[DATE] = [_session(source="manual")]
        self.assertEqual(self._kind(), "captured_other")

    def test_mixed_day_counts_as_scheduled(self):
        """The schedule delivered, whatever else also ran that day."""
        self.history.sessions[DATE] = [_session(source="scheduled"),
                                       _session(source="manual", images=5)]
        self.assertEqual(self._kind(), "captured")

    def test_folder_fallback_is_captured_other(self):
        """Frames on disk with no history entry: no proof the schedule was
        involved, so the untracked bucket."""
        self.p._folder_has_images.return_value = True
        self.assertEqual(self._kind(), "captured_other")

    def test_nothing_is_none(self):
        self.assertIsNone(self._kind())

    def test_folder_has_images_globs_the_date_folder(self):
        p = mock.MagicMock()
        p.snapshots_dir = Path(self._tmp.name) / "snaps"
        self.assertFalse(TwoMonthCalendar._folder_has_images(p, DAY))
        folder = p.snapshots_dir / DATE
        folder.mkdir(parents=True)
        self.assertFalse(TwoMonthCalendar._folder_has_images(p, DAY))
        (folder / "20260905-204100.jpg").write_bytes(b"")
        self.assertTrue(TwoMonthCalendar._folder_has_images(p, DAY))


class DateStatusTests(unittest.TestCase):
    def setUp(self):
        self.p = mock.MagicMock()
        self.p.selected_dates = set()

    def _status(self, d):
        return TwoMonthCalendar._get_date_status(self.p, d, d.strftime("%Y-%m-%d"))

    def test_past_day_takes_its_capture_kind(self):
        yesterday = date.today() - timedelta(days=1)
        for kind in ("captured", "captured_other"):
            self.p._get_capture_kind.return_value = kind
            self.assertEqual(self._status(yesterday), kind)

    def test_past_day_without_captures_is_past(self):
        self.p._get_capture_kind.return_value = None
        self.assertEqual(self._status(date.today() - timedelta(days=1)), "past")

    def test_future_and_today_unchanged(self):
        tomorrow = date.today() + timedelta(days=1)
        self.assertEqual(self._status(tomorrow), "future")
        self.p.selected_dates = {tomorrow.strftime("%Y-%m-%d")}
        self.assertEqual(self._status(tomorrow), "scheduled")
        self.p.selected_dates = set()
        self.assertEqual(self._status(date.today()), "today")

    def test_status_color_map_covers_captured_other(self):
        p = mock.MagicMock()
        p.COLORS = TwoMonthCalendar.COLORS
        color = TwoMonthCalendar._get_status_color(p, "captured_other")
        self.assertEqual(color, TwoMonthCalendar.COLORS["captured_other"])


class TooltipTextTests(unittest.TestCase):
    def test_full_multi_session_day(self):
        text = build_day_tooltip_text(DAY, [
            _session(source="scheduled", images=812, video=True),
            _session(source="manual", images=5,
                     start="2026-09-06T09:03:00", end="2026-09-06T09:05:00"),
        ], folder_has_images=False)
        self.assertEqual(text.splitlines(), [
            "Sat 2026-09-05",
            "Scheduled: 20:41 - 05:12, 812 frames, video created",
            "Manual: 09:03 - 09:05, 5 frames",
        ])

    def test_remote_label_and_failed_suffix(self):
        text = build_day_tooltip_text(DAY, [
            _session(source="remote", images=0, status="failed",
                     start="2026-09-05T21:00:00", end="2026-09-05T21:00:00"),
        ], folder_has_images=False)
        self.assertIn("Remote (NINA): 21:00 - 21:00, 0 frames (failed)", text)

    def test_singular_frame(self):
        text = build_day_tooltip_text(DAY, [_session(images=1)], False)
        self.assertIn("1 frame,", text + ",")
        self.assertNotIn("1 frames", text)

    def test_unparseable_time_shown_raw(self):
        """The file is hand-editable; a bad value must not break the calendar."""
        text = build_day_tooltip_text(DAY, [_session(start="garbage")], False)
        self.assertIn("garbage - 05:12", text)

    def test_folder_fallback_line(self):
        text = build_day_tooltip_text(DAY, [], folder_has_images=True)
        self.assertEqual(text.splitlines(),
                         ["Sat 2026-09-05", "Images on disk (no session record)"])

    def test_empty_day_yields_empty_text(self):
        """Empty text suppresses the ToolTip entirely."""
        self.assertEqual(build_day_tooltip_text(DAY, [], False), "")


class TooltipRefreshFolderCheckTests(unittest.TestCase):
    """_update_month_grid stats the snapshots folder only for past days.

    Every redraw (each calendar click) refreshes all cells' hover text; a
    future day can't have frames, so probing its folder is pure cost - and
    on a network output folder, dozens of round trips per click."""

    def _widget(self):
        p = mock.MagicMock()
        p.COLORS = TwoMonthCalendar.COLORS
        p.capture_history = None  # nothing recorded -> every day is a folder candidate
        p._day_labels = {}
        p._day_tooltips = {}
        for mo in (0, 1):
            p._day_labels[(mo, -1, 0)] = mock.MagicMock()  # month header
            for r in range(6):
                for c in range(7):
                    p._day_labels[(mo, r, c)] = (mock.MagicMock(), mock.MagicMock())
                    p._day_tooltips[(mo, r, c)] = mock.MagicMock()
        p._folder_has_images.return_value = False
        p._get_date_status.return_value = "past"
        p._get_status_color.return_value = "#E0E0E0"
        return p

    def test_past_month_checked_future_month_not(self):
        today = date.today()
        this_first = today.replace(day=1)
        prev_first = (this_first - timedelta(days=1)).replace(day=1)
        next_first = (this_first + timedelta(days=32)).replace(day=1)

        p = self._widget()
        TwoMonthCalendar._update_month_grid(p, 0, prev_first)
        checked = [c.args[0] for c in p._folder_has_images.call_args_list]
        self.assertEqual(len(checked), calendar.monthrange(prev_first.year, prev_first.month)[1])
        self.assertTrue(all(d < today for d in checked))

        p = self._widget()
        TwoMonthCalendar._update_month_grid(p, 1, next_first)
        p._folder_has_images.assert_not_called()

    def test_today_is_not_checked(self):
        """A running session has frames on disk but no record yet - "Images on
        disk (no session record)" for today would just be misleading."""
        today = date.today()
        p = self._widget()
        TwoMonthCalendar._update_month_grid(p, 0, today.replace(day=1))
        checked = [c.args[0] for c in p._folder_has_images.call_args_list]
        self.assertNotIn(today, checked)
        self.assertTrue(all(d < today for d in checked))


if __name__ == "__main__":
    unittest.main()
