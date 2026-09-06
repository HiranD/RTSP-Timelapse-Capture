"""
Unit tests for the calendar's capture-source coloring and hover text.

Widget methods are exercised unbound against a MagicMock stand-in (the
test_scheduler_autovideo.py pattern) so no Tk root is needed. The color rule
and the tooltip text builder are plain functions of a day's session list - the
list a redraw fetches once per cell and shares between the two.
"""

import calendar
import sys
import tempfile
import types
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from capture_history import CaptureSession  # noqa: E402
from calendar_widget import TwoMonthCalendar, build_day_tooltip_text  # noqa: E402

DAY = date(2026, 9, 5)
DATE = "20260905"


def _session(source="scheduled", images=800, video=False, status="completed",
             start="2026-09-05T20:41:00", end="2026-09-06T05:12:00"):
    return CaptureSession(date=DATE, start_time=start, end_time=end,
                          image_count=images, video_created=video,
                          status=status, source=source)


class CaptureKindTests(unittest.TestCase):
    """Which color bucket a past day lands in, from its session list."""

    def _kind(self, sessions, folder=False):
        return TwoMonthCalendar._capture_kind(sessions, folder)

    def test_scheduled_session_is_captured(self):
        self.assertEqual(self._kind([_session(source="scheduled")]), "captured")

    def test_manual_only_is_captured_other(self):
        self.assertEqual(self._kind([_session(source="manual")]), "captured_other")

    def test_mixed_day_counts_as_scheduled(self):
        """The schedule delivered, whatever else also ran that day."""
        self.assertEqual(self._kind([_session(source="scheduled"),
                                     _session(source="manual", images=5)]), "captured")

    def test_failed_scheduled_session_does_not_count(self):
        """A 0-frame scheduled night beside a real manual session: the
        schedule did not deliver, so the manual bucket."""
        self.assertEqual(self._kind([_session(source="scheduled", images=0, status="failed"),
                                     _session(source="manual")]), "captured_other")

    def test_folder_fallback_is_captured_other(self):
        """Frames on disk with no history entry: no proof the schedule was
        involved, so the untracked bucket."""
        self.assertEqual(self._kind([], folder=True), "captured_other")

    def test_failed_session_plus_frames_on_disk_is_captured_other(self):
        self.assertEqual(self._kind([_session(images=0, status="failed")], folder=True),
                         "captured_other")

    def test_nothing_is_none(self):
        self.assertIsNone(self._kind([]))
        self.assertIsNone(self._kind([_session(images=0, status="failed")]))

    def test_folder_has_images_globs_the_date_folder(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = mock.MagicMock()
        p.snapshots_dir = Path(tmp.name) / "snaps"
        self.assertFalse(TwoMonthCalendar._folder_has_images(p, DAY))
        folder = p.snapshots_dir / DATE
        folder.mkdir(parents=True)
        self.assertFalse(TwoMonthCalendar._folder_has_images(p, DAY))
        (folder / "20260905-204100.jpg").write_bytes(b"")
        self.assertTrue(TwoMonthCalendar._folder_has_images(p, DAY))

    def test_day_sessions_is_one_history_read(self):
        p = mock.MagicMock()
        p.capture_history.get_sessions_for_date.return_value = [_session()]
        self.assertEqual(len(TwoMonthCalendar._day_sessions(p, DAY)), 1)
        p.capture_history.get_sessions_for_date.assert_called_once_with(DATE)
        p.capture_history = None
        self.assertEqual(TwoMonthCalendar._day_sessions(p, DAY), [])


class DateStatusTests(unittest.TestCase):
    def setUp(self):
        self.p = mock.MagicMock()
        self.p.selected_dates = set()
        self.p._capture_kind = TwoMonthCalendar._capture_kind  # the real rule

    def _status(self, d, sessions=(), folder=False):
        return TwoMonthCalendar._get_date_status(self.p, d, d.strftime("%Y-%m-%d"),
                                                 list(sessions), folder)

    def test_past_day_takes_its_capture_kind(self):
        yesterday = date.today() - timedelta(days=1)
        self.assertEqual(self._status(yesterday, [_session(source="scheduled")]), "captured")
        self.assertEqual(self._status(yesterday, [_session(source="remote")]), "captured_other")
        self.assertEqual(self._status(yesterday, [], folder=True), "captured_other")

    def test_past_day_without_captures_is_past(self):
        self.assertEqual(self._status(date.today() - timedelta(days=1)), "past")

    def test_future_and_today_unchanged(self):
        """Sessions never color today or a future day - a day only earns a
        captured color once it's over."""
        tomorrow = date.today() + timedelta(days=1)
        self.assertEqual(self._status(tomorrow), "future")
        self.p.selected_dates = {tomorrow.strftime("%Y-%m-%d")}
        self.assertEqual(self._status(tomorrow), "scheduled")
        self.p.selected_dates = set()
        self.assertEqual(self._status(date.today(), [_session()]), "today")

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


class RedrawCostTests(unittest.TestCase):
    """_update_month_grid: one history read and at most one folder probe per
    cell, and only a past day without a successful record touches the folder.

    Every redraw (each calendar click) refreshes every cell's color and hover
    text; a future day can't have frames, and on a network output folder each
    probe is a round trip."""

    def _widget(self, sessions_by_date=None):
        p = mock.MagicMock()
        p.COLORS = TwoMonthCalendar.COLORS
        p.selected_dates = set()
        p._day_labels = {}
        p._day_tooltips = {}
        for mo in (0, 1):
            p._day_labels[(mo, -1, 0)] = mock.MagicMock()  # month header
            for r in range(6):
                for c in range(7):
                    p._day_labels[(mo, r, c)] = (mock.MagicMock(), mock.MagicMock())
                    p._day_tooltips[(mo, r, c)] = mock.MagicMock()
        # Real decision logic on the stand-in; only the data sources are faked.
        p.statuses = {}

        def status(d, s, sessions, folder):
            p.statuses[d] = TwoMonthCalendar._get_date_status(p, d, s, sessions, folder)
            return p.statuses[d]
        p._get_date_status = status
        p._capture_kind = TwoMonthCalendar._capture_kind
        p._get_status_color = types.MethodType(TwoMonthCalendar._get_status_color, p)
        by_date = sessions_by_date or {}
        p._day_sessions.side_effect = lambda d: list(by_date.get(d, []))
        p._folder_has_images.return_value = False
        return p

    @staticmethod
    def _probed(p):
        return [c.args[0] for c in p._folder_has_images.call_args_list]

    def test_past_month_probed_once_per_day_future_month_never(self):
        today = date.today()
        this_first = today.replace(day=1)
        prev_first = (this_first - timedelta(days=1)).replace(day=1)
        next_first = (this_first + timedelta(days=32)).replace(day=1)
        days = calendar.monthrange(prev_first.year, prev_first.month)[1]

        p = self._widget()
        TwoMonthCalendar._update_month_grid(p, 0, prev_first)
        probed = self._probed(p)
        self.assertEqual(len(probed), days)        # exactly one probe per past day...
        self.assertEqual(len(set(probed)), days)   # ...never the same day twice
        self.assertEqual(p._day_sessions.call_count, days)  # and one history read each

        p = self._widget()
        TwoMonthCalendar._update_month_grid(p, 1, next_first)
        p._folder_has_images.assert_not_called()

    def test_today_is_not_probed(self):
        """A running session has frames on disk but no record yet - "Images on
        disk (no session record)" for today would just be misleading."""
        today = date.today()
        p = self._widget()
        TwoMonthCalendar._update_month_grid(p, 0, today.replace(day=1))
        probed = self._probed(p)
        self.assertNotIn(today, probed)
        self.assertTrue(all(d < today for d in probed))

    def test_recorded_day_skips_the_folder_and_colors_from_the_same_list(self):
        """A day with a successful record never touches the folder, and its
        color and hover text come from the one list that was fetched."""
        yesterday = date.today() - timedelta(days=1)
        p = self._widget({yesterday: [_session(source="manual", images=42)]})
        TwoMonthCalendar._update_month_grid(p, 0, yesterday.replace(day=1))

        self.assertNotIn(yesterday, self._probed(p))
        self.assertEqual(p.statuses[yesterday], "captured_other")
        hover_texts = [c.args[0] for tip in p._day_tooltips.values()
                       for c in tip.update_text.call_args_list]
        self.assertTrue(any("Manual: 20:41 - 05:12, 42 frames" in t for t in hover_texts))

    def test_failed_only_day_still_probes_the_folder(self):
        """A 0-frame record proves nothing about frames on disk (an untracked
        capture that night), so the fallback still runs - once."""
        yesterday = date.today() - timedelta(days=1)
        p = self._widget({yesterday: [_session(source="remote", images=0, status="failed")]})
        p._folder_has_images.return_value = True
        TwoMonthCalendar._update_month_grid(p, 0, yesterday.replace(day=1))

        self.assertEqual(self._probed(p).count(yesterday), 1)
        self.assertEqual(p.statuses[yesterday], "captured_other")


if __name__ == "__main__":
    unittest.main()
