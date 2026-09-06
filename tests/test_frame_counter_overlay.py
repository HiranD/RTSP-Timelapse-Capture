"""
Unit tests for the frame-counter overlay setting.

The counter used to be a preset field (VideoExportSettings.add_timestamp), which
made unticking the checkbox ineffective for unattended renders: the scheduler and
POST /video/create build their settings from the *saved* preset, so a preset saved
with the counter on kept stamping every nightly video - and re-ticked the checkbox
on every restart. It now lives in config (ui.frame_counter_overlay) like the event
overlay, and is passed to prepare_export separately from the preset.
"""

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from ffmpeg_wrapper import FFmpegWrapper  # noqa: E402
from preset_manager import PresetManager, VideoExportSettings  # noqa: E402
from video_export_controller import VideoExportController  # noqa: E402


class FrameCounterSettingSourceTests(unittest.TestCase):
    """Where the frame-counter setting comes from: config, never the preset."""

    def test_ui_config_carries_the_frame_counter_preference(self):
        from config_manager import ConfigManager

        cfg = ConfigManager()
        self.assertFalse(cfg.ui.frame_counter_overlay)

        cfg.ui.frame_counter_overlay = True
        restored = ConfigManager()
        restored.from_dict(cfg.to_dict())
        self.assertTrue(restored.ui.frame_counter_overlay)

    def test_config_without_the_key_still_loads(self):
        """Configs written before the move must not fail to load."""
        from config_manager import ConfigManager

        cfg = ConfigManager()
        cfg.from_dict({"ui": {"window_width": 900}})
        self.assertEqual(cfg.ui.window_width, 900)
        self.assertFalse(cfg.ui.frame_counter_overlay)

    def test_presets_do_not_carry_the_frame_counter(self):
        """One source of truth: app_config.json. A preset must not be able to
        disagree with it, or switching preset would silently change the video."""
        settings = VideoExportSettings()
        self.assertFalse(hasattr(settings, "add_timestamp"))
        self.assertNotIn("add_timestamp", settings.to_dict())

    def test_legacy_preset_with_add_timestamp_still_loads(self):
        """A custom preset saved by an older version carries the stale key -
        exactly the preset that caused the stuck counter. It must load cleanly
        (and the key is simply dropped)."""
        legacy = {"framerate": 30, "quality": 22, "add_timestamp": True}
        settings = VideoExportSettings.from_dict(legacy)
        self.assertEqual(settings.framerate, 30)
        self.assertFalse(hasattr(settings, "add_timestamp"))

    def test_builtin_presets_have_no_frame_counter_field(self):
        for name, preset in PresetManager.BUILTIN_PRESETS.items():
            self.assertNotIn("add_timestamp", preset.to_dict(), name)


class FrameCounterExportPathTests(unittest.TestCase):
    """prepare_export threads the flag onto the job; build_command draws from it."""

    T0 = datetime(2026, 9, 5, 22, 0, 0)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.snapshots = Path(self._tmp.name) / "20260905"
        self.snapshots.mkdir()
        # Placeholder frames are enough: with events and temp copies off, nothing
        # opens them - scan_folder only parses the timestamped names.
        for i in range(3):
            when = self.T0 + timedelta(seconds=30 * i)
            (self.snapshots / f"{when:%Y%m%d-%H%M%S}.jpg").write_bytes(b"")
        self.ctrl = VideoExportController()
        self.output_file = Path(self._tmp.name) / "out.mp4"

    def _prepare(self, **kwargs):
        settings = VideoExportSettings(preserve_originals=False)
        ok, collection, msg = self.ctrl.scan_folder(self.snapshots)
        self.assertTrue(ok, msg)
        ok, job, msg = self.ctrl.prepare_export(
            settings, collection, self.output_file, **kwargs)
        self.assertTrue(ok, msg)
        return job

    def test_flag_defaults_off_on_the_job(self):
        self.assertFalse(self._prepare().draw_frame_counter)

    def test_flag_carried_onto_the_job(self):
        self.assertTrue(self._prepare(frame_counter=True).draw_frame_counter)

    def test_build_command_draws_the_counter_when_enabled(self):
        wrapper = FFmpegWrapper.__new__(FFmpegWrapper)  # skip the ffmpeg probe
        wrapper.ffmpeg_path = "ffmpeg"
        cmd = " ".join(wrapper.build_command("%06d.jpg", "out.mp4", add_timestamp=True))
        self.assertIn("drawtext", cmd)
        self.assertIn("frame_num", cmd)

    def test_build_command_is_clean_when_disabled(self):
        wrapper = FFmpegWrapper.__new__(FFmpegWrapper)
        wrapper.ffmpeg_path = "ffmpeg"
        cmd = " ".join(wrapper.build_command("%06d.jpg", "out.mp4", add_timestamp=False))
        self.assertNotIn("drawtext", cmd)


if __name__ == "__main__":
    unittest.main()
