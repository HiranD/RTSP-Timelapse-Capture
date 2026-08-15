"""
Unit tests for AstroScheduler's mid-window start gating (_check_schedule).

Pins the fix for "scheduler on + date ticked + already inside the window must
start capture": the old gate keyed on calendar-today and refused to START a
session after midnight (it only allowed continuing one), so enabling the
scheduler, ticking the date, or restarting the app at 01:00 silently skipped
the rest of the night. The night a moment belongs to is now decided by the
same folder-rollover rule that files frames (effective_date), and a start that
fails downstream must reset capture_active so the next poll retries.

No Tk and no astral: the clock and TwilightCalculator are patched; manual-mode
cases are pure time math.
"""

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import astro_scheduler  # noqa: E402
from astro_scheduler import AstroScheduler  # noqa: E402
from config_manager import ConfigManager  # noqa: E402


def _scheduler(dates, manual=True, manual_start="20:00", manual_end="08:00",
               rollover=12):
    cfg = ConfigManager()
    cfg.astro_schedule.scheduled_dates = list(dates)
    cfg.astro_schedule.use_manual_times = manual
    cfg.astro_schedule.manual_start_time = manual_start
    cfg.astro_schedule.manual_end_time = manual_end
    cfg.astro_schedule.latitude = 42.0
    cfg.astro_schedule.longitude = -7.0
    cfg.schedule.folder_rollover_hour = rollover

    started, stopped = [], []
    sched = AstroScheduler(
        config_manager=cfg,
        on_start_capture=lambda: started.append(True),
        on_stop_capture=lambda: stopped.append(True),
        on_log=lambda level, msg: None,
    )
    return sched, started, stopped


def _check_at(sched, moment):
    """Run one _check_schedule poll with the clock pinned to `moment`."""
    with mock.patch.object(astro_scheduler, "datetime", wraps=datetime) as md:
        md.now.return_value = moment
        sched._check_schedule()


class ManualModeMidWindowTests(unittest.TestCase):
    def test_after_midnight_start_for_yesterdays_ticked_night(self):
        # The regression pin: 01:30 is still the night of the 14th (rollover 12,
        # window 20:00-08:00). With the 14th ticked and no session active, the
        # poll must START one - the old code returned "session already ended".
        sched, started, _ = _scheduler(["2026-08-14"])
        _check_at(sched, datetime(2026, 8, 15, 1, 30))
        self.assertEqual(len(started), 1)
        self.assertTrue(sched.capture_active)

    def test_after_midnight_session_is_dated_to_the_owning_evening(self):
        sched, _, _ = _scheduler(["2026-08-14"])
        _check_at(sched, datetime(2026, 8, 15, 1, 30))
        self.assertEqual(sched.current_session_date, "20260814")

    def test_evening_start_for_todays_ticked_night(self):
        # Pin of existing behaviour: today ticked, inside the evening half.
        sched, started, _ = _scheduler(["2026-08-15"])
        _check_at(sched, datetime(2026, 8, 15, 22, 0))
        self.assertEqual(len(started), 1)
        self.assertEqual(sched.current_session_date, "20260815")

    def test_evening_does_not_start_on_yesterdays_tick(self):
        # 22:00 belongs to the 15th's night; only the 14th ticked -> nothing.
        sched, started, _ = _scheduler(["2026-08-14"])
        _check_at(sched, datetime(2026, 8, 15, 22, 0))
        self.assertEqual(started, [])
        self.assertFalse(sched.capture_active)

    def test_after_rollover_does_not_start_on_yesterdays_tick(self):
        # 13:00 (past rollover 12) belongs to the 15th; only the 14th ticked.
        sched, started, _ = _scheduler(["2026-08-14"])
        _check_at(sched, datetime(2026, 8, 15, 13, 0))
        self.assertEqual(started, [])

    def test_scheduled_night_outside_window_does_not_start(self):
        # Right night ticked, but 15:00 is outside 20:00-08:00.
        sched, started, _ = _scheduler(["2026-08-15"])
        _check_at(sched, datetime(2026, 8, 15, 15, 0))
        self.assertEqual(started, [])

    def test_unticking_the_night_stops_an_active_session(self):
        sched, _, stopped = _scheduler([])
        sched.capture_active = True
        sched.current_session_date = "20260814"
        _check_at(sched, datetime(2026, 8, 15, 1, 30))
        self.assertEqual(len(stopped), 1)
        self.assertFalse(sched.capture_active)


class RolloverHourTests(unittest.TestCase):
    """The owning date follows the configured rollover hour, not a fixed noon."""

    def test_before_custom_rollover_belongs_to_yesterday(self):
        sched, started, _ = _scheduler(["2026-08-14"], rollover=6)
        _check_at(sched, datetime(2026, 8, 15, 5, 0))
        self.assertEqual(len(started), 1)
        self.assertEqual(sched.current_session_date, "20260814")

    def test_after_custom_rollover_belongs_to_today(self):
        # 07:00 with rollover 6 is already the 15th's night; window 20:00-08:00
        # is still open, so with the 15th ticked it starts - dated the 15th.
        sched, started, _ = _scheduler(["2026-08-15"], rollover=6)
        _check_at(sched, datetime(2026, 8, 15, 7, 0))
        self.assertEqual(len(started), 1)
        self.assertEqual(sched.current_session_date, "20260815")


class TwilightModeMidWindowTests(unittest.TestCase):
    def _window(self, active, evening):
        window = mock.Mock()
        window.is_active_now.return_value = active
        window.date = evening
        midnight = datetime.combine(evening, datetime.min.time())
        window.darkness_start = midnight + timedelta(hours=21, minutes=43)
        window.darkness_end = midnight + timedelta(hours=30, minutes=12)
        return window

    def test_after_midnight_start_inside_active_window(self):
        sched, started, _ = _scheduler(["2026-08-14"], manual=False)
        window = self._window(active=True, evening=date(2026, 8, 14))
        with mock.patch.object(astro_scheduler, "TwilightCalculator") as calc:
            calc.return_value.get_tonight_window.return_value = window
            _check_at(sched, datetime(2026, 8, 15, 1, 30))
        self.assertEqual(len(started), 1)
        self.assertEqual(sched.current_session_date, "20260814")

    def test_inactive_window_does_not_start(self):
        sched, started, _ = _scheduler(["2026-08-14"], manual=False)
        window = self._window(active=False, evening=date(2026, 8, 14))
        with mock.patch.object(astro_scheduler, "TwilightCalculator") as calc:
            calc.return_value.get_tonight_window.return_value = window
            _check_at(sched, datetime(2026, 8, 15, 7, 30))
        self.assertEqual(started, [])


class StartFailureTests(unittest.TestCase):
    def test_notify_start_failed_resets_session_and_allows_retry(self):
        sched, started, stopped = _scheduler(["2026-08-15"])
        _check_at(sched, datetime(2026, 8, 15, 22, 0))
        self.assertTrue(sched.capture_active)

        # Downstream start failed (bad config, engine error): the scheduler
        # must forget the session - without firing on_session_complete/stop -
        # so the next poll tries again.
        sched.notify_start_failed()
        self.assertFalse(sched.capture_active)
        self.assertIsNone(sched.current_session_date)
        self.assertEqual(stopped, [])

        _check_at(sched, datetime(2026, 8, 15, 22, 1))
        self.assertEqual(len(started), 2)

    def test_panel_reports_failure_to_scheduler(self):
        # The panel-side wiring: _start_scheduled_capture must forward a failed
        # (ok, err) result to scheduler.notify_start_failed().
        from scheduling_panel import SchedulingPanel
        panel = mock.MagicMock()
        panel.start_capture_callback = mock.Mock(return_value=(False, "bad config"))
        SchedulingPanel._start_scheduled_capture(panel)
        panel.scheduler.notify_start_failed.assert_called_once()

    def test_panel_does_not_report_on_success(self):
        from scheduling_panel import SchedulingPanel
        panel = mock.MagicMock()
        panel.start_capture_callback = mock.Mock(return_value=(True, None))
        SchedulingPanel._start_scheduled_capture(panel)
        panel.scheduler.notify_start_failed.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
