"""
Unit tests for when an export may skip temp copies ("Preserve original filenames"
unticked).

The no-copy path hands ffmpeg "<source_folder>/%06d.jpg", so it only works for
frames already named 000000.jpg, 000001.jpg, ... The app names its snapshots by
capture time (YYYYMMDD-HHMMSS.jpg). Before this fix, unticking the box made every
export of them fail with "Could not find no file with path ...%06d.jpg".
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from video_export_controller import ImageCollection, VideoExportController  # noqa: E402
from preset_manager import VideoExportSettings  # noqa: E402
from ffmpeg_wrapper import FFmpegWrapper  # noqa: E402

TIME_NAMES = ["20261105-024205.jpg", "20261105-024235.jpg", "20261105-024305.jpg"]
NUMBERING_MESSAGE = "aren't named 000000.jpg"


class PrepareExportNumberingTests(unittest.TestCase):
    """prepare_export forces temp copies unless the frames are numbered."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.folder = self.base / "frames"
        self.folder.mkdir()
        self.ctrl = VideoExportController()
        self.messages = []

    def _make(self, names):
        # scan_folder reads names and stat() only, so empty files are enough.
        for name in names:
            (self.folder / name).write_bytes(b"")

    def _prepare(self, preserve_originals=False):
        ok, collection, msg = self.ctrl.scan_folder(self.folder)
        self.assertTrue(ok, msg)
        settings = VideoExportSettings(framerate=24, preserve_originals=preserve_originals)
        ok, job, msg = self.ctrl.prepare_export(
            settings, collection, self.base / "out.mp4",
            log_callback=self.messages.append,
            temp_dir=str(self.base))  # keep staging inside the test's tmp dir
        self.assertTrue(ok, msg)
        return job

    def _numbering_logged(self):
        return any(NUMBERING_MESSAGE in m for m in self.messages)

    def test_time_named_snapshots_get_temp_copies(self):
        self._make(TIME_NAMES)
        job = self._prepare()
        self.assertTrue(job.use_temp_copies)
        self.assertIsNotNone(job.temp_folder)
        self.assertTrue(self._numbering_logged(), self.messages)

    def test_numbered_frames_render_in_place(self):
        self._make(["000000.jpg", "000001.jpg", "000002.jpg"])
        job = self._prepare()
        self.assertFalse(job.use_temp_copies)
        self.assertIsNone(job.temp_folder)
        self.assertFalse(self._numbering_logged(), self.messages)

    def test_numbering_must_start_at_zero(self):
        self._make(["000001.jpg", "000002.jpg"])
        self.assertTrue(self._prepare().use_temp_copies)

    def test_gap_in_numbering_gets_copies(self):
        # ffmpeg stops reading at the first gap, so frames after it would be lost.
        self._make(["000000.jpg", "000002.jpg"])
        self.assertTrue(self._prepare().use_temp_copies)

    def test_mixed_names_get_copies(self):
        self._make(["000000.jpg", "000001.jpg", TIME_NAMES[0]])
        self.assertTrue(self._prepare().use_temp_copies)

    def test_ticked_box_copies_without_the_numbering_message(self):
        self._make(TIME_NAMES)
        job = self._prepare(preserve_originals=True)
        self.assertTrue(job.use_temp_copies)
        self.assertFalse(self._numbering_logged(), self.messages)


class IsNumberedSequenceTests(unittest.TestCase):
    """The helper on collections scan_folder can't produce, such as a `since` subset."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name)

    def _collection(self, names):
        images = [self.folder / name for name in names]
        for image in images:
            image.write_bytes(b"")
        return ImageCollection(images=images, total_count=len(images),
                               first_timestamp=None, last_timestamp=None,
                               duration_seconds=0, total_size_bytes=0,
                               source_folder=self.folder)

    def test_contiguous_run_from_zero(self):
        self.assertTrue(VideoExportController._is_numbered_sequence(
            self._collection(["000000.jpg", "000001.jpg"])))

    def test_upper_case_extension_counts(self):
        # Windows file names are case-insensitive, so ffmpeg opens these too.
        self.assertTrue(VideoExportController._is_numbered_sequence(
            self._collection(["000000.JPG", "000001.JPG"])))

    def test_later_numbered_file_outside_the_collection(self):
        # ffmpeg would read 000002.jpg as well, adding a frame the user didn't pick.
        collection = self._collection(["000000.jpg", "000001.jpg"])
        (self.folder / "000002.jpg").write_bytes(b"")
        self.assertFalse(VideoExportController._is_numbered_sequence(collection))

    def test_empty_collection(self):
        self.assertFalse(VideoExportController._is_numbered_sequence(self._collection([])))


_FFMPEG = FFmpegWrapper()


@unittest.skipUnless(_FFMPEG.check_installation()[0], "needs FFmpeg")
class TimeNamedExportEndToEndTest(unittest.TestCase):
    """The reported failure: time-named frames, box unticked, a real ffmpeg run."""

    def test_export_succeeds_with_preserve_originals_off(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = base / "Nueva carpeta"  # the space matters on Windows too
            folder.mkdir()
            for shade, name in enumerate(TIME_NAMES):
                Image.new("RGB", (64, 48), (shade * 80, 0, 0)).save(folder / name, "JPEG")

            ctrl = VideoExportController(_FFMPEG)
            ok, collection, msg = ctrl.scan_folder(folder)
            self.assertTrue(ok, msg)
            settings = VideoExportSettings(framerate=12, preserve_originals=False)
            output = base / "timelapse.mp4"
            ok, job, msg = ctrl.prepare_export(settings, collection, output,
                                               temp_dir=str(base))
            self.assertTrue(ok, msg)

            result = ctrl.export_video(job)

            self.assertTrue(result.success, result.message)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 0)
            # The originals are untouched.
            self.assertEqual(sorted(p.name for p in folder.iterdir()), TIME_NAMES)


if __name__ == "__main__":
    unittest.main()
