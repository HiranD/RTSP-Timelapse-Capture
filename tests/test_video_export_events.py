"""
Unit tests for event overlays inside the video export pipeline.

Covers where VideoExportController meets event_overlay: building the plan during
prepare_export, drawing captions while staging temp copies, and writing the
companion events CSV. FFmpeg is never invoked - only the stages either side of it.

Real (tiny) JPEGs are written here rather than empty placeholders, because the
overlay path actually opens and re-saves them.
"""

import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from event_log import EVENTS_FILENAME  # noqa: E402
from preset_manager import VideoExportSettings  # noqa: E402
from video_export_controller import VideoExportController  # noqa: E402

T0 = datetime(2026, 7, 25, 22, 0, 0)
FRAME_COUNT = 40
FRAME_INTERVAL = 30  # seconds, the app's default capture interval


class OverlaySettingSourceTests(unittest.TestCase):
    """Where the overlay setting comes from.

    Presets carry encoding choices and get switched freely; whether to burn in
    captions is a standing preference in UIConfig. This matters because the
    unattended render path (scheduler / POST /video/create) builds its settings
    from the saved preset - if it read the overlay flag from there, the Video
    Export tab's tick box would only ever affect the tab's own Export button.
    """

    def test_ui_config_carries_the_overlay_preference(self):
        from config_manager import ConfigManager

        cfg = ConfigManager()
        self.assertFalse(cfg.ui.event_overlay)
        self.assertEqual(cfg.ui.event_overlay_seconds, 4.0)

        cfg.ui.event_overlay = True
        cfg.ui.event_overlay_seconds = 6.0
        restored = ConfigManager()
        restored.from_dict(cfg.to_dict())
        self.assertTrue(restored.ui.event_overlay)
        self.assertEqual(restored.ui.event_overlay_seconds, 6.0)

    def test_presets_do_not_carry_overlay_settings(self):
        """One source of truth: app_config.json. A preset must not be able to
        disagree with it, or switching preset would silently change the video."""
        settings = VideoExportSettings()
        self.assertFalse(hasattr(settings, "event_overlay"))
        self.assertNotIn("event_overlay", settings.to_dict())

    def test_config_without_the_keys_still_loads(self):
        """Configs written before this feature must not fail to load."""
        from config_manager import ConfigManager

        cfg = ConfigManager()
        cfg.from_dict({"ui": {"window_width": 900, "preview_size": "large"}})
        self.assertEqual(cfg.ui.window_width, 900)
        self.assertFalse(cfg.ui.event_overlay)

    def test_hold_seconds_validated(self):
        from config_manager import ConfigManager

        cfg = ConfigManager()
        cfg.ui.event_overlay_seconds = 99
        valid, errors = cfg.validate()
        self.assertFalse(valid)
        self.assertTrue(any("overlay hold" in e for e in errors), errors)


class ExportEventOverlayTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.snapshots = self.root / "20260725"
        self.snapshots.mkdir()

        # Real JPEGs - the caption path opens and re-saves them.
        for i in range(FRAME_COUNT):
            when = T0 + timedelta(seconds=FRAME_INTERVAL * i)
            Image.new("RGB", (320, 180), (20, 30, 50)).save(
                self.snapshots / f"{when:%Y%m%d-%H%M%S}.jpg", "JPEG")

        self.output_file = self.root / "timelapse_20260725.mp4"
        self.ctrl = VideoExportController()
        self.messages = []

    def _write_events(self, *records):
        with open(self.snapshots / EVENTS_FILENAME, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

    def _default_events(self):
        self._write_events(
            {"time": "20260725-220500", "title": "Autofocus Complete",
             "detail": "HFR 2.31 -> 1.62", "category": "autofocus"},
            {"time": "20260725-221000", "title": "Meridian Flip"},
        )

    def _prepare(self, event_overlay=False, event_overlay_seconds=4.0, since=None, **settings_kw):
        """scan + prepare_export, returning the ExportJob.

        Overlay options are passed separately from `settings` on purpose: they live
        in config/app_config.json, not in a video preset.
        """
        settings = VideoExportSettings(framerate=24, **settings_kw)
        ok, collection, msg = self.ctrl.scan_folder(self.snapshots)
        self.assertTrue(ok, msg)
        ok, job, msg = self.ctrl.prepare_export(
            settings, collection, self.output_file, since=since,
            log_callback=self.messages.append,
            event_overlay=event_overlay, event_overlay_seconds=event_overlay_seconds)
        self.assertTrue(ok, msg)
        return job

    # ------------------------------------------------------------ scan_folder

    def test_scan_collects_a_timestamp_per_image(self):
        """Overlays bind events to frames through these, so they must stay aligned."""
        ok, collection, _msg = self.ctrl.scan_folder(self.snapshots)
        self.assertTrue(ok)
        self.assertEqual(len(collection.timestamps), collection.total_count)
        self.assertEqual(collection.timestamps[0], T0)
        self.assertEqual(collection.timestamps[0], collection.first_timestamp)
        self.assertEqual(collection.timestamps[-1], collection.last_timestamp)

    # --------------------------------------------------------- plan building

    def test_no_event_log_means_no_plan(self):
        job = self._prepare(event_overlay=True)
        self.assertIsNone(job.overlay_plan)

    def test_plan_built_even_when_overlay_disabled(self):
        """The plan also drives the CSV, so item 5 works without burning captions in."""
        self._default_events()
        job = self._prepare(event_overlay=False)
        self.assertIsNotNone(job.overlay_plan)
        self.assertEqual(len(job.overlay_plan.captions), 2)

    def test_unparseable_frame_names_skip_overlays_with_a_message(self):
        """Misaligned timestamps would put captions on the wrong frames - skip instead."""
        from PIL import Image

        self._default_events()
        Image.new("RGB", (320, 180)).save(self.snapshots / "not-a-timestamp.jpg", "JPEG")

        job = self._prepare(event_overlay=True)
        self.assertIsNone(job.overlay_plan)
        self.assertTrue(any("no timestamp" in m for m in self.messages), self.messages)

    # ------------------------------------------------------- temp-copy forcing

    def test_overlays_force_temp_copies(self):
        """Captions are drawn onto the copies, so the temp path is mandatory."""
        self._default_events()
        job = self._prepare(event_overlay=True, preserve_originals=False)
        self.assertTrue(job.use_temp_copies)
        self.assertIsNotNone(job.temp_folder)
        self.assertTrue(any("preserve originals" in m for m in self.messages), self.messages)

    def test_no_forcing_when_overlay_disabled(self):
        self._default_events()
        job = self._prepare(event_overlay=False, preserve_originals=False)
        self.assertFalse(job.use_temp_copies)

    def test_no_forcing_when_session_logged_nothing(self):
        job = self._prepare(event_overlay=True, preserve_originals=False)
        self.assertFalse(job.use_temp_copies)

    # -------------------------------------------------------------- drawing

    def _staged_bytes(self, job):
        ok, msg = self.ctrl._prepare_temp_images(job, None, self.messages.append)
        self.assertTrue(ok, msg)
        return {p.name: p.read_bytes() for p in sorted(job.temp_folder.glob("*.jpg"))}

    def test_captions_drawn_only_on_frames_in_range(self):
        self._default_events()
        job = self._prepare(event_overlay=True)
        staged = self._staged_bytes(job)

        self.assertEqual(len(staged), FRAME_COUNT)
        originals = {p.name: p.read_bytes() for p in sorted(self.snapshots.glob("*.jpg"))}
        original_bytes = list(originals.values())

        # Frame 0 (22:00) is before the first event - untouched byte-for-byte.
        self.assertEqual(staged["000000.jpg"], original_bytes[0])
        # Frame 10 (22:05) carries the autofocus caption - re-encoded, so different.
        self.assertNotEqual(staged["000010.jpg"], original_bytes[10])

    def test_nothing_redrawn_when_overlay_disabled(self):
        """Plan present (for the CSV) but drawing off: every frame is a plain copy."""
        self._default_events()
        job = self._prepare(event_overlay=False)
        staged = self._staged_bytes(job)

        originals = [p.read_bytes() for p in sorted(self.snapshots.glob("*.jpg"))]
        self.assertEqual(list(staged.values()), originals)

    def test_all_frames_staged_even_when_drawing(self):
        """Every source frame must reach the temp folder or FFmpeg's %06d run breaks."""
        self._default_events()
        job = self._prepare(event_overlay=True)
        staged = self._staged_bytes(job)
        self.assertEqual(sorted(staged), [f"{i:06d}.jpg" for i in range(FRAME_COUNT)])

    # ------------------------------------------------------------------ CSV

    def test_csv_written_beside_the_video(self):
        self._default_events()
        job = self._prepare(event_overlay=True)
        self.ctrl._write_event_csv(job, self.messages.append)

        csv_path = self.root / "timelapse_20260725.events.csv"
        self.assertTrue(csv_path.exists())
        with open(csv_path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["title"] for r in rows],
                         ["Autofocus Complete", "Meridian Flip"])
        self.assertEqual(rows[0]["wall_clock"], "2026-07-25 22:05:00")

    def test_csv_written_even_with_overlay_disabled(self):
        self._default_events()
        job = self._prepare(event_overlay=False)
        self.ctrl._write_event_csv(job, self.messages.append)
        self.assertTrue((self.root / "timelapse_20260725.events.csv").exists())

    def test_no_csv_when_no_events(self):
        job = self._prepare(event_overlay=True)
        self.ctrl._write_event_csv(job, self.messages.append)
        self.assertFalse((self.root / "timelapse_20260725.events.csv").exists())

    def test_csv_name_survives_dots_in_the_video_name(self):
        """with_suffix() would replace the wrong part of 'timelapse_2026.07.25.mp4'."""
        self._default_events()
        self.output_file = self.root / "timelapse_2026.07.25.mp4"
        job = self._prepare(event_overlay=True)
        self.ctrl._write_event_csv(job, self.messages.append)
        self.assertTrue((self.root / "timelapse_2026.07.25.events.csv").exists())


if __name__ == "__main__":
    unittest.main()
