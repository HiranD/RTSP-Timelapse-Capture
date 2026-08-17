"""
Unit tests for CaptureEngine window timing: _calculate_end_time and the
start-time wait.

Pins the regression that silently killed scheduled nights: _wait_for_start_time
truncated its wait with int() and woke fractionally BEFORE the start time, and
_calculate_end_time - which since c848e3b runs right after the wake, before the
first connect - classified that instant as "before the window" and returned an
end time hours in the past, so the capture loop exited with zero frames
("Capture completed - reached end time").

No camera and no waiting: the module clock and stop_event are mocked.
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import capture_engine  # noqa: E402
from capture_engine import CaptureEngine  # noqa: E402


def _engine(start, end):
    return CaptureEngine({
        "camera": {"ip_address": "cam", "username": "u", "password": "p",
                   "stream_path": "/s"},
        "schedule": {"start_time": start, "end_time": end,
                     "folder_rollover_hour": 12},
        "capture": {"interval_seconds": 30, "jpeg_quality": 95,
                    "output_folder": ".", "max_retries": 3},
    })


class CalculateEndTimeTests(unittest.TestCase):
    def _end_at(self, moment, start, end):
        eng = _engine(start, end)
        with mock.patch.object(capture_engine, "datetime", wraps=datetime) as md:
            md.now.return_value = moment
            return eng._calculate_end_time()

    def test_overnight_wake_fractionally_before_start(self):
        # The regression pin: woken 0.7s before the 20:00 start, the end must
        # be tomorrow 07:00 - not this morning's 07:00, 13 hours in the past.
        end_dt = self._end_at(datetime(2026, 8, 14, 19, 59, 59, 300000),
                              "20:00", "07:00")
        self.assertEqual(end_dt, datetime(2026, 8, 15, 7, 0))

    def test_overnight_evening_inside_window(self):
        end_dt = self._end_at(datetime(2026, 8, 14, 22, 30), "20:00", "07:00")
        self.assertEqual(end_dt, datetime(2026, 8, 15, 7, 0))

    def test_overnight_early_morning_inside_window(self):
        end_dt = self._end_at(datetime(2026, 8, 15, 2, 0), "20:00", "07:00")
        self.assertEqual(end_dt, datetime(2026, 8, 15, 7, 0))

    def test_same_day_woken_just_before_start(self):
        end_dt = self._end_at(datetime(2026, 8, 14, 7, 59, 59, 400000),
                              "08:00", "18:00")
        self.assertEqual(end_dt, datetime(2026, 8, 14, 18, 0))

    def test_same_day_inside_window(self):
        end_dt = self._end_at(datetime(2026, 8, 14, 12, 0), "08:00", "18:00")
        self.assertEqual(end_dt, datetime(2026, 8, 14, 18, 0))

    def test_same_day_after_end_rolls_to_tomorrow(self):
        # Pin of existing behaviour: started after today's end -> tomorrow's end.
        end_dt = self._end_at(datetime(2026, 8, 14, 19, 0), "08:00", "18:00")
        self.assertEqual(end_dt, datetime(2026, 8, 15, 18, 0))


class WaitForStartTimeTests(unittest.TestCase):
    """The wait must round UP: int() truncation woke the thread up to ~1s
    before the start time, which is what exposed the end-time bug above."""

    def _wait_timeout(self, moment, start, end):
        eng = _engine(start, end)
        eng.stop_event = mock.Mock()
        eng.stop_event.wait.return_value = False  # wait "expires", not stopped
        with mock.patch.object(capture_engine, "datetime", wraps=datetime) as md:
            md.now.return_value = moment
            self.assertTrue(eng._wait_for_start_time())
        return eng.stop_event.wait.call_args.kwargs["timeout"]

    def test_overnight_wait_never_shorter_than_remaining(self):
        moment = datetime(2026, 8, 14, 10, 0, 0, 300000)
        exact = (datetime(2026, 8, 14, 20, 0) - moment).total_seconds()
        self.assertGreaterEqual(self._wait_timeout(moment, "20:00", "07:00"), exact)

    def test_same_day_wait_never_shorter_than_remaining(self):
        moment = datetime(2026, 8, 14, 6, 0, 0, 250000)
        exact = (datetime(2026, 8, 14, 8, 0) - moment).total_seconds()
        self.assertGreaterEqual(self._wait_timeout(moment, "08:00", "18:00"), exact)


if __name__ == "__main__":
    unittest.main(verbosity=2)
