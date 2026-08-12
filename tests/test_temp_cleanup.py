"""
Unit tests for the export temp-folder cleanup and stale-folder sweep in
src/video_export_controller.py.

Background: the final rmtree of an export's .temp_export_* folder can lose a race
against an external handle (indexer/AV/folder sync), leaving an empty folder
behind. _cleanup_temp now retries and reports; _sweep_stale_temp_folders removes
abandoned leftovers before the next export. No GUI / ffmpeg involved - both
methods are exercised directly with a mock ffmpeg wrapper.
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from video_export_controller import (  # noqa: E402
    STALE_TEMP_AGE_SECONDS, VideoExportController,
)


class TempCleanupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.controller = VideoExportController(Mock())
        self.messages = []
        self.log = self.messages.append

    def tearDown(self):
        self._tmp.cleanup()

    def _job(self, temp_folder):
        # _cleanup_temp only reads job.temp_folder, so a stand-in is enough.
        return SimpleNamespace(temp_folder=temp_folder)

    def _make_temp_folder(self, name=".temp_export_20260809_072915", age_seconds=None):
        folder = self.dir / name
        folder.mkdir()
        if age_seconds is not None:
            stamp = time.time() - age_seconds
            os.utime(folder, (stamp, stamp))
        return folder

    # ------------------------------------------------------------ _cleanup_temp

    def test_cleanup_removes_folder(self):
        folder = self._make_temp_folder()
        (folder / "000001.jpg").write_bytes(b"x")
        self.controller._cleanup_temp(self._job(folder), self.log)
        self.assertFalse(folder.exists())
        self.assertEqual(self.messages, [])

    def test_cleanup_retries_after_transient_failure(self):
        folder = self._make_temp_folder()
        real_rmtree = __import__("shutil").rmtree
        calls = []

        def flaky_rmtree(path):
            calls.append(path)
            if len(calls) == 1:
                raise OSError("held by another process")
            real_rmtree(path)

        with patch("video_export_controller.shutil.rmtree", side_effect=flaky_rmtree), \
             patch("video_export_controller.time.sleep"):
            self.controller._cleanup_temp(self._job(folder), self.log)

        self.assertEqual(len(calls), 2)
        self.assertFalse(folder.exists())
        self.assertEqual(self.messages, [])

    def test_cleanup_reports_when_all_attempts_fail(self):
        folder = self._make_temp_folder()
        with patch("video_export_controller.shutil.rmtree",
                   side_effect=OSError("held")) as rmtree, \
             patch("video_export_controller.time.sleep"):
            self.controller._cleanup_temp(self._job(folder), self.log)

        self.assertEqual(rmtree.call_count, 3)
        self.assertTrue(folder.exists())
        self.assertEqual(len(self.messages), 1)
        self.assertIn(folder.name, self.messages[0])

    def test_cleanup_noop_without_folder(self):
        self.controller._cleanup_temp(self._job(None), self.log)
        self.controller._cleanup_temp(self._job(self.dir / "missing"), self.log)
        self.assertEqual(self.messages, [])

    # ------------------------------------------- _sweep_stale_temp_folders

    def test_sweep_removes_old_and_keeps_fresh(self):
        stale = self._make_temp_folder(".temp_export_20260809_072915",
                                       age_seconds=STALE_TEMP_AGE_SECONDS + 60)
        fresh = self._make_temp_folder(".temp_export_20260812_073224")

        self.controller._sweep_stale_temp_folders(self.dir, self.log)

        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists())
        self.assertEqual(len(self.messages), 1)
        self.assertIn(stale.name, self.messages[0])

    def test_sweep_ignores_other_entries(self):
        video = self.dir / "timelapse-2026-08-11.mp4"
        video.write_bytes(b"mp4")
        other_dir = self.dir / "archive"
        other_dir.mkdir()
        stamp = time.time() - (STALE_TEMP_AGE_SECONDS + 60)
        os.utime(other_dir, (stamp, stamp))

        self.controller._sweep_stale_temp_folders(self.dir, self.log)

        self.assertTrue(video.exists())
        self.assertTrue(other_dir.exists())
        self.assertEqual(self.messages, [])

    def test_sweep_survives_undeletable_folder(self):
        self._make_temp_folder(age_seconds=STALE_TEMP_AGE_SECONDS + 60)
        with patch("video_export_controller.shutil.rmtree",
                   side_effect=OSError("held")):
            self.controller._sweep_stale_temp_folders(self.dir, self.log)
        self.assertEqual(self.messages, [])


if __name__ == "__main__":
    unittest.main()
