"""
Unit tests for VideoExportController.delete_rendered_snapshots().

This is the single implementation of a destructive action shared by three render
paths (scheduler, remote API, and the Video Export tab), so the point of these
tests is that it removes exactly what was rendered - never more - and never
raises: a failed cleanup must not turn a successful export into a reported
failure. A folder goes only once nothing but its events.jsonl is left.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from video_export_controller import VideoExportController  # noqa: E402


def _make_folder(base: Path, name: str, frames, events=True) -> Path:
    folder = base / name
    folder.mkdir()
    for frame in frames:
        (folder / frame).write_bytes(b"x")
    if events:
        (folder / "events.jsonl").write_bytes(b"{}")
    return folder


class DeleteRenderedSnapshotsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.messages = []

    def test_deletes_only_listed_files(self):
        folder = _make_folder(self.base, "20260725",
                              ["20260725-140000.jpg", "20260725-140030.jpg",
                               "20260725-220000.jpg", "20260725-220030.jpg"])
        rendered = [folder / "20260725-220000.jpg", folder / "20260725-220030.jpg"]
        ok = VideoExportController.delete_rendered_snapshots(rendered, self.messages.append)
        self.assertTrue(ok)
        self.assertTrue(folder.exists())
        self.assertFalse((folder / "20260725-220000.jpg").exists())
        self.assertFalse((folder / "20260725-220030.jpg").exists())
        self.assertTrue((folder / "20260725-140000.jpg").exists())
        self.assertTrue((folder / "20260725-140030.jpg").exists())

    def test_keeps_events_jsonl_when_other_frames_remain(self):
        """Remaining frames may be rendered later - their overlay still needs the log."""
        folder = _make_folder(self.base, "20260725",
                              ["20260725-140000.jpg", "20260725-220000.jpg"])
        VideoExportController.delete_rendered_snapshots(
            [folder / "20260725-220000.jpg"], self.messages.append)
        self.assertTrue((folder / "events.jsonl").exists())
        self.assertTrue(any("Kept folder" in m for m in self.messages), self.messages)

    def test_removes_folder_when_only_events_jsonl_remains(self):
        folder = _make_folder(self.base, "20260725",
                              ["20260725-220000.jpg", "20260725-220030.jpg"])
        ok = VideoExportController.delete_rendered_snapshots(
            [folder / "20260725-220000.jpg", folder / "20260725-220030.jpg"],
            self.messages.append)
        self.assertTrue(ok)
        self.assertFalse(folder.exists())

    def test_full_folder_list_removes_folder(self):
        """Equivalence pin with the old whole-folder delete: rendering everything
        in a folder and deleting it leaves nothing behind, events.jsonl included."""
        folder = _make_folder(self.base, "20260725",
                              ["20260725-220000.jpg", "20260725-220030.jpg"])
        ok = VideoExportController.delete_rendered_snapshots(
            sorted(folder.glob("*.jpg")), self.messages.append)
        self.assertTrue(ok)
        self.assertFalse(folder.exists())
        self.assertTrue(any("Deleting snapshot folder" in m for m in self.messages), self.messages)
        self.assertTrue(any("deleted" in m.lower() for m in self.messages), self.messages)

    def test_multi_folder_list_handled_per_folder(self):
        """A rollover-split session: one folder empties (removed), one keeps frames."""
        first = _make_folder(self.base, "20260725", ["20260725-230000.jpg"])
        second = _make_folder(self.base, "20260726",
                              ["20260726-010000.jpg", "20260726-120000.jpg"])
        ok = VideoExportController.delete_rendered_snapshots(
            [first / "20260725-230000.jpg", second / "20260726-010000.jpg"],
            self.messages.append)
        self.assertTrue(ok)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        self.assertTrue((second / "20260726-120000.jpg").exists())
        self.assertTrue((second / "events.jsonl").exists())

    def test_missing_files_are_success(self):
        """The caller's intent is 'they shouldn't be there' - already gone satisfies that."""
        folder = _make_folder(self.base, "20260725", ["20260725-220000.jpg"], events=False)
        ok = VideoExportController.delete_rendered_snapshots(
            [folder / "20260725-220000.jpg", folder / "20260725-999999.jpg"],
            self.messages.append)
        self.assertTrue(ok)
        self.assertFalse(folder.exists())

    def test_empty_list_is_success_noop(self):
        ok = VideoExportController.delete_rendered_snapshots([], self.messages.append)
        self.assertTrue(ok)
        self.assertEqual(self.messages, [], "a no-op shouldn't log anything")

    def test_rmtree_failure_is_reported_not_raised(self):
        """A locked folder must not escape as an exception into the export result."""
        folder = _make_folder(self.base, "20260725", ["20260725-220000.jpg"])
        with mock.patch("video_export_controller.shutil.rmtree",
                        side_effect=OSError("in use by another process")):
            ok = VideoExportController.delete_rendered_snapshots(
                [folder / "20260725-220000.jpg"], self.messages.append)

        self.assertFalse(ok)
        self.assertTrue(folder.exists(), "folder should survive a failed delete")
        self.assertTrue(any("Failed to delete" in m for m in self.messages), self.messages)

    def test_unlink_failure_is_reported_not_raised(self):
        folder = _make_folder(self.base, "20260725", ["20260725-220000.jpg"])
        with mock.patch.object(Path, "unlink", side_effect=OSError("locked")):
            ok = VideoExportController.delete_rendered_snapshots(
                [folder / "20260725-220000.jpg"], self.messages.append)

        self.assertFalse(ok)
        self.assertTrue((folder / "20260725-220000.jpg").exists())
        self.assertTrue(any("Failed to delete" in m for m in self.messages), self.messages)

    def test_works_without_a_log_callback(self):
        folder = _make_folder(self.base, "20260725", ["20260725-220000.jpg"])
        ok = VideoExportController.delete_rendered_snapshots([folder / "20260725-220000.jpg"])
        self.assertTrue(ok)
        self.assertFalse(folder.exists())


if __name__ == "__main__":
    unittest.main()
