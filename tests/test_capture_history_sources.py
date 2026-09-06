"""
Unit tests for the capture-history source field and multi-session store.

History used to hold ONE session per date (last-wins), and only the scheduler
ever wrote it - manual/NINA capture days lost their calendar mark once their
snapshot folders were deleted. Sessions now accumulate per date and carry a
`source` ("scheduled" | "remote" | "manual"); the on-disk JSON shape (a flat
"sessions" list) is unchanged, so files round-trip with older versions.
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from capture_history import CaptureHistoryManager, CaptureSession  # noqa: E402

DATE = "20260905"


def _dt(hour, minute=0, day=5):
    return datetime(2026, 9, day, hour, minute, 0)


class CaptureSessionCompatTests(unittest.TestCase):
    """Loading entries written by other versions must never break."""

    def test_legacy_dict_without_source_defaults_to_scheduled(self):
        """Only the scheduler ever wrote history before the field existed, so
        "scheduled" is the factually correct default for legacy entries."""
        legacy = {"date": DATE, "start_time": "2026-09-05T20:00:00",
                  "end_time": "2026-09-06T05:00:00", "image_count": 800,
                  "video_created": True, "status": "completed"}
        session = CaptureSession.from_dict(legacy)
        self.assertEqual(session.source, "scheduled")

    def test_unknown_future_key_is_dropped_not_fatal(self):
        """An unknown key used to TypeError - and the loader's broad except
        then silently discarded the ENTIRE history file."""
        data = {"date": DATE, "start_time": "2026-09-05T20:00:00",
                "end_time": "2026-09-06T05:00:00", "image_count": 1,
                "video_created": False, "status": "completed",
                "some_future_field": 123}
        session = CaptureSession.from_dict(data)
        self.assertEqual(session.date, DATE)
        self.assertFalse(hasattr(session, "some_future_field"))


class MultiSessionStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.mgr = CaptureHistoryManager(config_dir=self.dir)

    def test_legacy_file_without_source_loads(self):
        legacy = {"sessions": [
            {"date": DATE, "start_time": "2026-09-05T20:00:00",
             "end_time": "2026-09-06T05:00:00", "image_count": 800,
             "video_created": False, "status": "completed"}]}
        (self.dir / "capture_history.json").write_text(json.dumps(legacy))

        mgr = CaptureHistoryManager(config_dir=self.dir)
        sessions = mgr.get_sessions_for_date(DATE)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].source, "scheduled")
        self.assertTrue(mgr.has_capture(DATE))

    def test_sessions_on_the_same_date_accumulate(self):
        """The old last-wins overwrite let a 5-frame morning test erase the
        real 800-frame night - the exact record the calendar colors need."""
        self.mgr.record_session(DATE, _dt(20), _dt(5, day=6), 800, source="scheduled")
        self.mgr.record_session(DATE, _dt(9, day=6), _dt(9, 5, day=6), 5, source="manual")

        reloaded = CaptureHistoryManager(config_dir=self.dir)
        sessions = reloaded.get_sessions_for_date(DATE)
        self.assertEqual([s.source for s in sessions], ["scheduled", "manual"])
        self.assertEqual([s.image_count for s in sessions], [800, 5])
        self.assertTrue(reloaded.has_capture(DATE))
        self.assertEqual(reloaded.get_captured_dates(), [DATE])

    def test_has_scheduled_capture_distinguishes_sources(self):
        self.mgr.record_session(DATE, _dt(20), _dt(23), 100, source="manual")
        self.mgr.record_session("20260906", _dt(20, day=6), _dt(23, day=6), 100,
                                source="scheduled")
        self.assertFalse(self.mgr.has_scheduled_capture(DATE))
        self.assertTrue(self.mgr.has_scheduled_capture("20260906"))
        # Mixed day: any scheduled session makes it scheduled.
        self.mgr.record_session(DATE, _dt(23, 30), _dt(23, 45), 10, source="scheduled")
        self.assertTrue(self.mgr.has_scheduled_capture(DATE))

    def test_zero_frame_session_is_failed_and_not_captured(self):
        self.mgr.record_session(DATE, _dt(20), _dt(20, 1), 0, source="remote")
        self.assertEqual(self.mgr.get_sessions_for_date(DATE)[0].status, "failed")
        self.assertFalse(self.mgr.has_capture(DATE))
        self.assertEqual(self.mgr.get_captured_dates(), [])

    def test_get_session_shim_returns_the_last_session(self):
        self.mgr.record_session(DATE, _dt(20), _dt(23), 800, source="scheduled")
        self.mgr.record_session(DATE, _dt(9, day=6), _dt(9, 5, day=6), 5, source="manual")
        self.assertEqual(self.mgr.get_session(DATE).source, "manual")
        self.assertIsNone(self.mgr.get_session("20991231"))

    def test_update_video_created_targets_most_recent_completed(self):
        """The render was built from frames - a trailing 0-frame failed session
        doesn't have any, so it must not receive the video mark. And the
        replace()-based update must keep every other field (the old
        field-by-field rebuild silently dropped newly added ones)."""
        self.mgr.record_session(DATE, _dt(20), _dt(5, day=6), 800, source="remote")
        self.mgr.record_session(DATE, _dt(9, day=6), _dt(9, 1, day=6), 0, source="manual")

        self.mgr.update_video_created(DATE, True)

        sessions = CaptureHistoryManager(config_dir=self.dir).get_sessions_for_date(DATE)
        completed, failed = sessions
        self.assertTrue(completed.video_created)
        self.assertEqual(completed.source, "remote")  # preserved through the update
        self.assertEqual(completed.image_count, 800)
        self.assertFalse(failed.video_created)

    def test_update_video_created_on_unknown_date_is_a_noop(self):
        self.mgr.update_video_created("20991231", True)  # must not raise
        self.assertEqual(self.mgr.get_sessions_for_date("20991231"), [])


if __name__ == "__main__":
    unittest.main()
