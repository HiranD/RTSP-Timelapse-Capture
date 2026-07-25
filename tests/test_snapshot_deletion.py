"""
Unit tests for VideoExportController.delete_source_snapshots().

This is the single implementation of a destructive action shared by three render
paths (scheduler, remote API, and the Video Export tab), so the point of these
tests is that it removes what it should and never raises - a failed cleanup must
not be able to turn a successful export into a reported failure.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from video_export_controller import VideoExportController  # noqa: E402


class DeleteSourceSnapshotsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "20260725"
        self.folder.mkdir()
        for name in ("20260725-220000.jpg", "20260725-220030.jpg", "events.jsonl"):
            (self.folder / name).write_bytes(b"x")
        self.messages = []

    def test_removes_the_folder_and_its_contents(self):
        ok = VideoExportController.delete_source_snapshots(self.folder, self.messages.append)
        self.assertTrue(ok)
        self.assertFalse(self.folder.exists())

    def test_logs_what_it_did(self):
        VideoExportController.delete_source_snapshots(self.folder, self.messages.append)
        self.assertTrue(any("Deleting snapshot folder" in m for m in self.messages), self.messages)
        self.assertTrue(any("deleted" in m.lower() for m in self.messages), self.messages)

    def test_missing_folder_is_success_not_an_error(self):
        """The caller's intent is 'it shouldn't be there' - already gone satisfies that."""
        missing = Path(self._tmp.name) / "never-existed"
        ok = VideoExportController.delete_source_snapshots(missing, self.messages.append)
        self.assertTrue(ok)
        self.assertEqual(self.messages, [], "a no-op shouldn't log anything")

    def test_failure_is_reported_not_raised(self):
        """A locked folder must not escape as an exception into the export result."""
        with mock.patch("video_export_controller.shutil.rmtree",
                        side_effect=OSError("in use by another process")):
            ok = VideoExportController.delete_source_snapshots(self.folder, self.messages.append)

        self.assertFalse(ok)
        self.assertTrue(self.folder.exists(), "folder should survive a failed delete")
        self.assertTrue(any("Failed to delete" in m for m in self.messages), self.messages)

    def test_works_without_a_log_callback(self):
        ok = VideoExportController.delete_source_snapshots(self.folder)
        self.assertTrue(ok)
        self.assertFalse(self.folder.exists())


if __name__ == "__main__":
    unittest.main()
