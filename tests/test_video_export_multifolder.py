"""
Unit tests for VideoExportController.scan_folders() and the multi-folder
handling in prepare_export().

A session that crosses the folder rollover hour spans two date folders; the
session-aware render path scans every folder from the session's start onward
and stitches the results into one collection. scan_folder reads names and
stat() only, so empty placeholder files suffice (no real images).
"""

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from video_export_controller import VideoExportController  # noqa: E402
from preset_manager import VideoExportSettings  # noqa: E402


class ScanFoldersTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        # A midnight-crossing session under rollover 0: evening half, morning half.
        self.first = self._folder("20260725", ["20260725-230000.jpg", "20260725-233000.jpg"])
        self.second = self._folder("20260726", ["20260726-000000.jpg", "20260726-003000.jpg"])
        self.ctrl = VideoExportController()

    def _folder(self, name, files):
        folder = self.base / name
        folder.mkdir()
        for file_name in files:
            (folder / file_name).write_bytes(b"")
        return folder

    def test_merges_folders_in_timestamp_order(self):
        ok, coll, msg = self.ctrl.scan_folders([self.first, self.second])
        self.assertTrue(ok, msg)
        self.assertEqual(coll.total_count, 4)
        self.assertEqual([img.name for img in coll.images],
                         ["20260725-230000.jpg", "20260725-233000.jpg",
                          "20260726-000000.jpg", "20260726-003000.jpg"])
        self.assertEqual(coll.first_timestamp, datetime(2026, 7, 25, 23, 0, 0))
        self.assertEqual(coll.last_timestamp, datetime(2026, 7, 26, 0, 30, 0))
        self.assertEqual(coll.duration_seconds, 90 * 60)
        self.assertEqual(len(coll.timestamps), coll.total_count)

    def test_since_filters_across_folders(self):
        ok, coll, _ = self.ctrl.scan_folders([self.first, self.second],
                                             since=datetime(2026, 7, 25, 23, 30, 0))
        self.assertTrue(ok)
        self.assertEqual([img.name for img in coll.images],
                         ["20260725-233000.jpg", "20260726-000000.jpg",
                          "20260726-003000.jpg"])

    def test_source_folders_lists_contributors(self):
        ok, coll, _ = self.ctrl.scan_folders([self.first, self.second])
        self.assertTrue(ok)
        self.assertEqual(coll.source_folder, self.first)
        self.assertEqual(coll.source_folders, [self.first, self.second])

    def test_non_contributing_folders_skipped(self):
        """Missing or empty folders are skips, not errors - only an empty merge fails."""
        empty = self.base / "20260727"
        empty.mkdir()
        missing = self.base / "20260728"
        ok, coll, _ = self.ctrl.scan_folders([self.first, self.second, empty, missing])
        self.assertTrue(ok)
        self.assertEqual(coll.total_count, 4)
        self.assertEqual(coll.source_folders, [self.first, self.second])

    def test_all_empty_is_an_error_with_folder_count(self):
        ok, coll, msg = self.ctrl.scan_folders([self.first, self.second],
                                               since=datetime(2026, 7, 26, 12, 0, 0))
        self.assertFalse(ok)
        self.assertIsNone(coll)
        self.assertIn("at/after", msg)
        self.assertIn("2 folder(s)", msg)

    def test_single_folder_equivalent_to_scan_folder(self):
        ok_single, single, _ = self.ctrl.scan_folder(self.first)
        ok_multi, multi, _ = self.ctrl.scan_folders([self.first])
        self.assertTrue(ok_single and ok_multi)
        self.assertEqual(single.images, multi.images)
        self.assertEqual(single.timestamps, multi.timestamps)
        self.assertEqual(single.total_count, multi.total_count)

    def test_unparseable_names_excluded_when_since_set(self):
        """Mirrors scan_folder: with `since` every kept frame has a timestamp,
        so the merged sort is total and overlays stay aligned."""
        (self.first / "notes.jpg").write_bytes(b"")
        ok, coll, _ = self.ctrl.scan_folders([self.first, self.second],
                                             since=datetime(2026, 7, 25, 0, 0, 0))
        self.assertTrue(ok)
        self.assertNotIn("notes.jpg", [img.name for img in coll.images])
        self.assertTrue(all(coll.timestamps))


class PrepareExportMultiFolderTests(unittest.TestCase):
    """A merged collection can't render in place - the non-temp path feeds ffmpeg
    a single %06d pattern inside source_folder - so temp copies must be forced."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        for name, files in (("20260725", ["20260725-230000.jpg"]),
                            ("20260726", ["20260726-000000.jpg"])):
            folder = self.base / name
            folder.mkdir()
            for file_name in files:
                (folder / file_name).write_bytes(b"")
        self.ctrl = VideoExportController()
        self.messages = []

    def test_multi_folder_forces_temp_copies(self):
        ok, coll, msg = self.ctrl.scan_folders(
            [self.base / "20260725", self.base / "20260726"])
        self.assertTrue(ok, msg)
        settings = VideoExportSettings(framerate=24, preserve_originals=False)
        ok, job, msg = self.ctrl.prepare_export(
            settings, coll, self.base / "out.mp4",
            log_callback=self.messages.append,
            temp_dir=str(self.base))  # keep staging inside the test's tmp dir
        self.assertTrue(ok, msg)
        self.assertTrue(job.use_temp_copies)
        self.assertTrue(any("Multi-folder render" in m for m in self.messages),
                        self.messages)

    def test_single_folder_still_respects_preserve_originals_false(self):
        ok, coll, _ = self.ctrl.scan_folder(self.base / "20260725")
        self.assertTrue(ok)
        settings = VideoExportSettings(framerate=24, preserve_originals=False)
        ok, job, _ = self.ctrl.prepare_export(settings, coll, self.base / "out.mp4")
        self.assertTrue(ok)
        self.assertFalse(job.use_temp_copies)


if __name__ == "__main__":
    unittest.main()
