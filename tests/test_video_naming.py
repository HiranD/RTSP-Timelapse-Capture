"""
Unit tests for the shared video filename convention.

Every render path (scheduled stop, remote /video/create, the scheduler's
nightly auto-video) must produce the same dashed name the Video Export tab
suggests - two formats side by side in the output folder is what prompted this.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gui_app import video_filename  # noqa: E402


class VideoFilenameTests(unittest.TestCase):
    def test_dashed_iso_shape(self):
        self.assertEqual(video_filename("20260729", "mp4"), "timelapse-2026-07-29.mp4")

    def test_extension_follows_preset_format(self):
        self.assertEqual(video_filename("20260101", "mkv"), "timelapse-2026-01-01.mkv")


if __name__ == "__main__":
    unittest.main()
