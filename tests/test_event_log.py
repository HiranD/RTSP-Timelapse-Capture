"""
Unit tests for src/event_log.py (the session event store).

No GUI / Tkinter involved - the store is Tk-agnostic by design. The directory
provider is a plain lambda pointing at a temp folder, standing in for
CaptureEngine.ensure_date_dir.
"""

import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from event_log import (  # noqa: E402
    EVENTS_FILENAME, MAX_TITLE, EventLog, SessionEvent, read_events,
)


class EventLogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.log = EventLog(dir_provider=lambda: str(self.dir))

    def tearDown(self):
        self._tmp.cleanup()

    def _lines(self):
        path = self.dir / EVENTS_FILENAME
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    # ------------------------------------------------------------- session gate

    def test_rejects_when_no_session(self):
        """Events with no running capture have no frames to attach to (-> 409)."""
        ok, err, stored = self.log.record("Sequence Started")
        self.assertFalse(ok)
        self.assertEqual(err, "not capturing")
        self.assertIsNone(stored)
        self.assertFalse((self.dir / EVENTS_FILENAME).exists())

    def test_rejects_after_session_ends(self):
        self.log.begin_session()
        self.log.record("During")
        self.log.end_session()

        ok, err, _ = self.log.record("After")
        self.assertFalse(ok)
        self.assertEqual(err, "not capturing")
        self.assertEqual([r["title"] for r in self._lines()], ["During"])

    def test_begin_session_clears_recent_but_keeps_file(self):
        """A new session starts with an empty in-memory list; the log keeps appending."""
        self.log.begin_session()
        self.log.record("First night")
        self.log.end_session()

        self.log.begin_session()
        self.assertEqual(self.log.recent(), [])
        self.log.record("Second night")

        self.assertEqual([r["title"] for r in self.log.recent()], ["Second night"])
        self.assertEqual([r["title"] for r in self._lines()], ["First night", "Second night"])

    # ------------------------------------------------------------------ record

    def test_records_all_fields(self):
        self.log.begin_session()
        when = datetime(2026, 7, 25, 23, 5, 18)
        ok, err, stored = self.log.record(
            "Autofocus Complete", "HFR 2.31 -> 1.62", "autofocus", when,
            {"hfr_before": 2.31, "hfr_after": 1.62},
        )

        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(stored["time"], "20260725-230518")
        self.assertEqual(stored["title"], "Autofocus Complete")
        self.assertEqual(stored["detail"], "HFR 2.31 -> 1.62")
        self.assertEqual(stored["category"], "autofocus")
        self.assertEqual(stored["data"]["hfr_after"], 1.62)
        self.assertEqual(self._lines(), [stored])

    def test_optional_fields_omitted_when_empty(self):
        self.log.begin_session()
        _ok, _err, stored = self.log.record("Meridian Flip")
        self.assertEqual(set(stored), {"time", "title"})

    def test_missing_title_rejected(self):
        self.log.begin_session()
        for bad in (None, "", "   ", 42):
            ok, err, _ = self.log.record(bad)
            self.assertFalse(ok, f"expected {bad!r} to be rejected")
            self.assertEqual(err, "missing title")

    def test_title_clamped_not_rejected(self):
        """An over-long title is truncated - a shortened caption beats a lost event."""
        self.log.begin_session()
        _ok, _err, stored = self.log.record("x" * (MAX_TITLE + 50))
        self.assertEqual(len(stored["title"]), MAX_TITLE)

    def test_newlines_stripped_so_one_event_is_one_line(self):
        """A newline in the title would otherwise split the JSONL record in two."""
        self.log.begin_session()
        self.log.record("Line one\nLine two", detail="a\tb")

        raw = (self.dir / EVENTS_FILENAME).read_text(encoding="utf-8")
        self.assertEqual(raw.count("\n"), 1)
        self.assertEqual(self._lines()[0]["title"], "Line oneLine two")

    def test_non_dict_data_dropped(self):
        self.log.begin_session()
        _ok, _err, stored = self.log.record("Event", data=["not", "a", "dict"])
        self.assertNotIn("data", stored)

    def test_write_failure_reported_not_raised(self):
        """An unwritable session folder is an error return, not an exception."""
        log = EventLog(dir_provider=lambda: str(self.dir / "does" / "not" / "exist"))
        log.begin_session()
        ok, err, _ = log.record("Event")
        self.assertFalse(ok)
        self.assertEqual(err, "could not write event log")

    def test_concurrent_appends_all_land_intact(self):
        """Events arrive on HTTP worker threads, so appends must not interleave."""
        self.log.begin_session()
        threads = [
            threading.Thread(target=lambda n=n: self.log.record(f"Event {n}"))
            for n in range(40)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        titles = {r["title"] for r in self._lines()}
        self.assertEqual(titles, {f"Event {n}" for n in range(40)})

    # -------------------------------------------------------------- read_events

    def test_read_events_round_trip_sorted(self):
        self.log.begin_session()
        self.log.record("Later", when=datetime(2026, 7, 25, 23, 0, 0))
        self.log.record("Earlier", when=datetime(2026, 7, 25, 22, 0, 0))

        events = read_events(self.dir)
        self.assertEqual([e.title for e in events], ["Earlier", "Later"])

    def test_read_events_since_filter(self):
        self.log.begin_session()
        self.log.record("Old session", when=datetime(2026, 7, 25, 18, 0, 0))
        self.log.record("This session", when=datetime(2026, 7, 25, 22, 0, 0))

        events = read_events(self.dir, since=datetime(2026, 7, 25, 21, 0, 0))
        self.assertEqual([e.title for e in events], ["This session"])

    def test_read_events_missing_file(self):
        self.assertEqual(read_events(self.dir), [])

    def test_read_events_skips_corrupt_lines(self):
        """A truncated final line must cost one event, not the whole export."""
        self.log.begin_session()
        self.log.record("Good one")
        with open(self.dir / EVENTS_FILENAME, "a", encoding="utf-8") as f:
            f.write('{"time": "20260725-230000", "title": "Truncated"')  # no newline, no close

        events = read_events(self.dir)
        self.assertEqual([e.title for e in events], ["Good one"])

    def test_read_events_skips_records_missing_required_fields(self):
        with open(self.dir / EVENTS_FILENAME, "w", encoding="utf-8") as f:
            f.write(json.dumps({"time": "20260725-230000"}) + "\n")          # no title
            f.write(json.dumps({"title": "No timestamp"}) + "\n")            # no time
            f.write(json.dumps({"time": "not-a-time", "title": "Bad"}) + "\n")
            f.write(json.dumps({"time": "20260725-231500", "title": "Fine"}) + "\n")

        events = read_events(self.dir)
        self.assertEqual([e.title for e in events], ["Fine"])


class SessionEventTests(unittest.TestCase):
    def test_from_dict_rejects_non_dict(self):
        self.assertIsNone(SessionEvent.from_dict("nope"))
        self.assertIsNone(SessionEvent.from_dict(None))

    def test_from_dict_round_trip(self):
        original = SessionEvent(
            time=datetime(2026, 7, 25, 1, 56, 41),
            title="Filter: L-Extreme",
            category="filter",
        )
        restored = SessionEvent.from_dict(original.to_dict())
        self.assertEqual(restored.time, original.time)
        self.assertEqual(restored.title, original.title)
        self.assertEqual(restored.category, original.category)
        self.assertIsNone(restored.detail)


if __name__ == "__main__":
    unittest.main()
