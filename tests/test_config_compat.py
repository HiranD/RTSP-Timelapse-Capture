"""
Unit tests for loading configs written by a different app version.

ConfigManager.from_dict() expands each section into a dataclass, so a key the
current version no longer has (e.g. "force_tcp", removed in 3.5.0) used to raise
TypeError - swallowed by load_from_file(), which silently reset every setting.
Unknown keys must be dropped instead, leaving the known ones intact.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config_manager import ConfigManager  # noqa: E402


class UnknownKeyToleranceTests(unittest.TestCase):
    def test_removed_camera_key_does_not_lose_other_settings(self):
        # A pre-3.5.0 camera section: force_tcp is gone, everything else stays.
        mgr = ConfigManager()
        mgr.from_dict({
            "camera": {
                "ip_address": "10.0.0.5:1554",
                "username": "operator",
                "password": "pw",
                "stream_path": "/cam/realmonitor?channel=1&subtype=0",
                "force_tcp": True,
            }
        })

        self.assertEqual(mgr.camera.ip_address, "10.0.0.5:1554")
        self.assertEqual(mgr.camera.username, "operator")
        self.assertEqual(mgr.camera.stream_path, "/cam/realmonitor?channel=1&subtype=0")
        self.assertFalse(hasattr(mgr.camera, "force_tcp"))

    def test_unknown_key_in_other_sections_is_dropped(self):
        # The same tolerance applies to every section, not just camera.
        mgr = ConfigManager()
        mgr.from_dict({
            "capture": {"interval_seconds": 45, "some_future_option": "x"},
            "schedule": {"start_time": "21:30", "legacy_key": 1},
            "ui": {"preview_size": "large", "gone_in_a_future_version": False},
            "astro_schedule": {"latitude": 51.5, "obsolete": None},
            "remote_api": {"port": 9000, "obsolete": None},
        })

        self.assertEqual(mgr.capture.interval_seconds, 45)
        self.assertEqual(mgr.schedule.start_time, "21:30")
        self.assertEqual(mgr.ui.preview_size, "large")
        self.assertEqual(mgr.astro_schedule.latitude, 51.5)
        self.assertEqual(mgr.remote_api.port, 9000)

    def test_old_config_file_loads_and_saves_clean(self):
        # End to end through the file layer: an old file loads, and the stale key
        # is gone from what gets written back.
        old_config = ConfigManager().to_dict()
        old_config["camera"]["force_tcp"] = True
        old_config["camera"]["stream_path"] = "/s0"

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "app_config.json")
            with open(path, "w") as f:
                json.dump(old_config, f)

            mgr = ConfigManager()
            success, message = mgr.load_from_file(path)
            self.assertTrue(success, message)
            self.assertEqual(mgr.camera.stream_path, "/s0")

            success, message = mgr.save_to_file(path)
            self.assertTrue(success, message)
            with open(path) as f:
                saved = json.load(f)

        self.assertNotIn("force_tcp", saved["camera"])
        self.assertEqual(saved["camera"]["stream_path"], "/s0")

    def test_delete_snapshots_migrates_from_astro_schedule(self):
        """The key moved to `ui` when it stopped being scheduler-only.

        Anyone upgrading has it under astro_schedule; losing the value would silently
        turn off deletion for people who had opted into it.
        """
        mgr = ConfigManager()
        mgr.from_dict({
            "ui": {"window_width": 900},
            "astro_schedule": {"delete_snapshots_after_video": True},
        })
        self.assertTrue(mgr.ui.delete_snapshots_after_video)
        self.assertEqual(mgr.ui.window_width, 900)

    def test_delete_snapshots_migrates_without_a_ui_section(self):
        """An older config may have astro_schedule but no ui section at all."""
        mgr = ConfigManager()
        mgr.from_dict({"astro_schedule": {"delete_snapshots_after_video": True}})
        self.assertTrue(mgr.ui.delete_snapshots_after_video)

    def test_explicit_ui_value_wins_over_stale_legacy_key(self):
        """Once written under `ui`, a leftover astro_schedule key must not override it."""
        mgr = ConfigManager()
        mgr.from_dict({
            "ui": {"delete_snapshots_after_video": False},
            "astro_schedule": {"delete_snapshots_after_video": True},
        })
        self.assertFalse(mgr.ui.delete_snapshots_after_video)

    def test_delete_snapshots_defaults_off_and_legacy_key_is_dropped(self):
        mgr = ConfigManager()
        mgr.from_dict({"ui": {}, "astro_schedule": {}})
        self.assertFalse(mgr.ui.delete_snapshots_after_video)
        # The stale key disappears from what gets written back.
        self.assertNotIn("delete_snapshots_after_video", mgr.to_dict()["astro_schedule"])
        self.assertIn("delete_snapshots_after_video", mgr.to_dict()["ui"])

    def test_pre_mqtt_config_keeps_discord_delivery(self):
        """A config written before MQTT delivery existed must keep uploading to Discord.

        The new keys simply default; anything else would silently switch an
        existing rig's nightly upload to a broker that isn't there.
        """
        mgr = ConfigManager()
        mgr.from_dict({
            "astro_schedule": {
                "discord_webhook_url": "https://discord.com/api/webhooks/1/abc",
                "discord_max_video_size_mb": 25,
                "discord_auto_quality_reduction": True,
            }
        })

        self.assertEqual(mgr.astro_schedule.delivery_method, "discord")
        self.assertEqual(mgr.astro_schedule.discord_webhook_url,
                         "https://discord.com/api/webhooks/1/abc")
        self.assertEqual(mgr.astro_schedule.discord_max_video_size_mb, 25)
        self.assertEqual(mgr.astro_schedule.mqtt_broker_host, "127.0.0.1")
        self.assertEqual(mgr.astro_schedule.mqtt_broker_port, 1883)
        self.assertEqual(mgr.astro_schedule.mqtt_base_topic, "rtsp-timelapse")
        self.assertEqual(mgr.astro_schedule.mqtt_qos, 1)
        self.assertFalse(mgr.astro_schedule.mqtt_use_tls)

    def test_config_with_utf8_bom_loads(self):
        """A BOM must not wipe the user's settings.

        Editing app_config.json in Notepad, or writing it from PowerShell's
        Set-Content -Encoding utf8, prepends a UTF-8 BOM. Loading with the locale
        default encoding then raises JSONDecodeError, and because the caller falls
        back to defaults the failure is silent and total - camera, output folders
        and API port all appear to reset themselves.
        """
        config = ConfigManager().to_dict()
        config["camera"]["ip_address"] = "192.168.171.22"
        config["ui"]["last_video_export_dir"] = r"C:\videos"

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "app_config.json")
            raw = json.dumps(config).encode("utf-8")
            with open(path, "wb") as f:
                f.write(b"\xef\xbb\xbf" + raw)  # UTF-8 BOM

            mgr = ConfigManager()
            success, message = mgr.load_from_file(path)

        self.assertTrue(success, message)
        self.assertEqual(mgr.camera.ip_address, "192.168.171.22")
        self.assertEqual(mgr.ui.last_video_export_dir, r"C:\videos")

    def test_saved_config_has_no_bom_and_survives_non_ascii(self):
        """We write plain UTF-8, and a non-ASCII path round-trips intact."""
        mgr = ConfigManager()
        mgr.capture.output_folder = r"C:\Users\Jörg\snapshots"

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "app_config.json")
            success, message = mgr.save_to_file(path)
            self.assertTrue(success, message)

            with open(path, "rb") as f:
                head = f.read(3)
            self.assertNotEqual(head, b"\xef\xbb\xbf", "config was written with a BOM")

            reloaded = ConfigManager()
            success, message = reloaded.load_from_file(path)

        self.assertTrue(success, message)
        self.assertEqual(reloaded.capture.output_folder, r"C:\Users\Jörg\snapshots")


if __name__ == "__main__":
    unittest.main(verbosity=2)
