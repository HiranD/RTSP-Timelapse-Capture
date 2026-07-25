"""
Unit tests for capture_engine.effective_date() - the single home of the
folder_rollover_hour rule. ensure_date_dir files frames (and the event log)
with it, and the session-aware render path uses it to map a session's start
time back to its starting date folder, so both sides must agree exactly.
"""

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from capture_engine import effective_date  # noqa: E402


class EffectiveDateTests(unittest.TestCase):
    def test_before_rollover_belongs_to_previous_day(self):
        self.assertEqual(effective_date(datetime(2026, 7, 26, 3, 0), 12),
                         date(2026, 7, 25))

    def test_at_rollover_hour_belongs_to_same_day(self):
        self.assertEqual(effective_date(datetime(2026, 7, 26, 12, 0), 12),
                         date(2026, 7, 26))

    def test_after_rollover_belongs_to_same_day(self):
        self.assertEqual(effective_date(datetime(2026, 7, 26, 20, 0), 12),
                         date(2026, 7, 26))

    def test_rollover_zero_never_rolls_back(self):
        """Rollover 0 means folders switch exactly at midnight."""
        self.assertEqual(effective_date(datetime(2026, 7, 26, 0, 0), 0),
                         date(2026, 7, 26))
        self.assertEqual(effective_date(datetime(2026, 7, 26, 23, 59), 0),
                         date(2026, 7, 26))

    def test_rollover_23_boundary(self):
        self.assertEqual(effective_date(datetime(2026, 7, 26, 22, 59), 23),
                         date(2026, 7, 25))
        self.assertEqual(effective_date(datetime(2026, 7, 26, 23, 0), 23),
                         date(2026, 7, 26))

    def test_year_boundary(self):
        self.assertEqual(effective_date(datetime(2027, 1, 1, 3, 0), 12),
                         date(2026, 12, 31))


if __name__ == "__main__":
    unittest.main()
