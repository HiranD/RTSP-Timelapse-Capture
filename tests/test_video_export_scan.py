"""
Unit tests for VideoExportController.scan_folder() timestamp filtering.

Covers the `since` filter used by POST /video/create to render only one
session's frames when several sessions share a date folder. Files are created
with the real snapshot naming (YYYYMMDD-HHMMSS.jpg); scan_folder reads the names
and stat() only, so empty placeholder files are sufficient (no real images).
"""

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from video_export_controller import VideoExportController  # noqa: E402


class ScanFolderSinceTests(unittest.TestCase):
    NAMES = [
        "20250620-200000.jpg",
        "20250620-203000.jpg",
        "20250620-210000.jpg",
        "20250620-213000.jpg",
    ]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name)
        for name in self.NAMES:
            (self.folder / name).write_bytes(b"")
        self.ctrl = VideoExportController()

    def test_no_since_returns_all(self):
        ok, coll, _ = self.ctrl.scan_folder(self.folder)
        self.assertTrue(ok)
        self.assertEqual(coll.total_count, 4)

    def test_since_keeps_frames_at_or_after(self):
        # 21:00:00 is inclusive -> keeps 21:00 and 21:30.
        ok, coll, _ = self.ctrl.scan_folder(self.folder, since=datetime(2025, 6, 20, 21, 0, 0))
        self.assertTrue(ok)
        self.assertEqual(coll.total_count, 2)
        self.assertEqual(coll.images[0].name, "20250620-210000.jpg")
        self.assertEqual(coll.images[-1].name, "20250620-213000.jpg")

    def test_since_after_all_frames_errors(self):
        ok, coll, msg = self.ctrl.scan_folder(self.folder, since=datetime(2025, 6, 20, 22, 0, 0))
        self.assertFalse(ok)
        self.assertIsNone(coll)
        self.assertIn("at/after", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
