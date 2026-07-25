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
import gui_app  # noqa: E402
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

    def test_end_equals_now_runs_until_next_occurrence(self):
        # Degenerate but intentional: with "Now", End Time == the current minute
        # makes start_time == end_time. This is NOT a special case - it's the same
        # "stop at the next occurrence of End Time" rule that drives overnight
        # windows, so the session runs ~24h rather than ending instantly. Pinned
        # here so the consistent behavior isn't "fixed" into an inconsistency.
        eng = _engine(start=self.now_str, end=self.now_str)
        self.assertTrue(eng._wait_for_start_time())  # still starts immediately
        end_dt = eng._calculate_end_time()
        self.assertGreater(end_dt, datetime.now() + timedelta(hours=23))
        self.assertLess(end_dt, datetime.now() + timedelta(hours=25))


class _FakeWidget:
    """Minimal stand-in for a Tk entry/var exposing just .get()."""

    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


def _bare_app(mode, start_field, saved_start="22:40"):
    """An app instance (no Tk) with the widgets update_config_from_ui() reads."""
    app = gui_app.RTSPTimelapseGUI.__new__(gui_app.RTSPTimelapseGUI)
    app.config_manager = ConfigManager()
    app.config_manager.schedule.start_time = saved_start
    app.start_mode_var = _FakeWidget(mode)
    app.ip_entry = _FakeWidget("192.168.0.101")
    app.username_entry = _FakeWidget("admin")
    app.password_entry = _FakeWidget("pw")
    app.stream_path_entry = _FakeWidget("/stream1")
    app.start_time_entry = _FakeWidget(start_field)
    app.end_time_entry = _FakeWidget("07:00")
    app.interval_entry = _FakeWidget("30")
    app.output_entry = _FakeWidget("snapshots")
    app.jpeg_quality_entry = _FakeWidget("95")
    app.proactive_reconnect_entry = _FakeWidget("300")
    app.rollover_hour_spinbox = _FakeWidget("12")
    return app


class UpdateConfigStartModeTests(unittest.TestCase):
    """PR #18 review: 'Now' must ignore the greyed Start Time field entirely."""

    def test_now_mode_does_not_copy_greyed_field(self):
        # An invalid value left in the greyed field must neither overwrite the
        # saved scheduled Start Time nor fail validation.
        app = _bare_app(mode="now", start_field="08", saved_start="22:40")
        app.update_config_from_ui()
        self.assertEqual(app.config_manager.schedule.start_time, "22:40")
        valid, errors = app.config_manager.validate()
        self.assertTrue(valid, errors)

    def test_at_time_mode_copies_the_field(self):
        # In the normal path the typed Start Time is still saved.
        app = _bare_app(mode="at_time", start_field="21:15", saved_start="22:40")
        app.update_config_from_ui()
        self.assertEqual(app.config_manager.schedule.start_time, "21:15")


if __name__ == "__main__":
    unittest.main(verbosity=2)
