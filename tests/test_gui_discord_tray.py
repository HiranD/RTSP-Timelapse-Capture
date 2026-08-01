"""
Unit tests for the GUI Discord-upload and system-tray helpers in src/gui_app.py.

These cover pure, side-effect-free helpers, so they construct the app via
``__new__`` (bypassing ``__init__`` and Tk) and run headless on any platform:

- ``_create_tray_image`` must produce a valid icon without raising. ImageDraw.textsize
  was removed in Pillow 10 (which requirements.txt pins); this guards against the
  label-rendering path regressing.
- ``_encode_multipart_formdata`` must emit a well-formed body where the file part
  carries a filename + Content-Type and the raw bytes (not a stringified tuple).
"""

import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import gui_app  # noqa: E402
from PIL import Image  # noqa: E402


def _bare_app():
    """An app instance without __init__/Tk — only safe for self-contained helpers."""
    return gui_app.RTSPTimelapseGUI.__new__(gui_app.RTSPTimelapseGUI)


class CreateTrayImageTests(unittest.TestCase):
    """Cover the generated-badge fallback path of _create_tray_image."""

    def setUp(self):
        # Force the fallback by pointing the icon lookup at a path that doesn't
        # exist — otherwise the committed assets/icon.ico loads and returns a
        # 256x256 image instead of the 64x64 generated badge.
        patcher = mock.patch.object(
            gui_app, "get_app_icon_path", return_value=Path("does-not-exist.ico")
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_returns_valid_rgba_icon(self):
        img = _bare_app()._create_tray_image()
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, "RGBA")

    def test_icon_is_actually_drawn(self):
        # The circle (and label) must paint opaque pixels — a fully transparent
        # image would mean the drawing path silently failed.
        img = _bare_app()._create_tray_image()
        _, max_alpha = img.getchannel("A").getextrema()
        self.assertGreater(max_alpha, 0)


class TrayImageFromAssetTests(unittest.TestCase):
    """Cover the path where the committed app icon is loaded for the tray."""

    def test_loads_committed_icon_when_present(self):
        if not gui_app.get_app_icon_path().exists():
            self.skipTest("assets/icon.ico not present")
        img = _bare_app()._create_tray_image()
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.mode, "RGBA")


class EncodeMultipartTests(unittest.TestCase):
    def setUp(self):
        self.app = _bare_app()

    def test_content_type_declares_boundary(self):
        body, content_type = self.app._encode_multipart_formdata([("a", b"1")])
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
        boundary = content_type.split("boundary=", 1)[1]
        # Body opens with the boundary and ends with the closing delimiter.
        self.assertIn(f"--{boundary}\r\n".encode(), body)
        self.assertTrue(body.endswith(f"--{boundary}--\r\n".encode()))

    def test_simple_field_encoded_as_form_field(self):
        body, _ = self.app._encode_multipart_formdata([("content", b"hello")])
        self.assertIn(b'Content-Disposition: form-data; name="content"\r\n\r\n', body)
        self.assertIn(b"hello", body)

    def test_file_field_has_filename_content_type_and_raw_bytes(self):
        raw = b"\x00\x01BINARY\xff"
        body, _ = self.app._encode_multipart_formdata(
            [("file", ("clip.mp4", raw, "video/mp4"))]
        )
        self.assertIn(
            b'Content-Disposition: form-data; name="file"; filename="clip.mp4"\r\n',
            body,
        )
        self.assertIn(b"Content-Type: video/mp4\r\n", body)
        # The raw bytes must appear verbatim — not a stringified (filename, bytes,
        # type) tuple, which is what the old len()-based dispatch produced.
        self.assertIn(raw, body)
        self.assertNotIn(b"('clip.mp4'", body)

    def test_mixed_payload_and_file(self):
        body, _ = self.app._encode_multipart_formdata(
            [("payload_json", b'{"k":1}'), ("file", ("v.mp4", b"DATA", "video/mp4"))]
        )
        self.assertIn(b'name="payload_json"', body)
        self.assertIn(b'name="file"; filename="v.mp4"', body)
        self.assertIn(b'{"k":1}', body)
        self.assertIn(b"DATA", body)


class DiscordUploadFilenameTests(unittest.TestCase):
    """The upload must carry the render's date-stamped name.

    An oversized video is re-encoded into .discord_encode/discord_crf<N>.mp4, and
    that scratch name used to be what Discord showed - so every night's post was
    called "discord_crf32.mp4". No socket is opened: urlopen is patched.
    """

    def setUp(self):
        import tempfile
        from config_manager import AstroScheduleConfig

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.video = Path(self._tmp.name) / "timelapse-2026-07-25.mp4"
        self.video.write_bytes(b"\x00" * (2 * 1024 * 1024))

        self.app = _bare_app()
        self.app.log_message = mock.MagicMock()
        self.app.config_manager = mock.MagicMock()
        self.app.config_manager.astro_schedule = AstroScheduleConfig(
            discord_webhook_url="https://discord.com/api/webhooks/1/abc",
            discord_max_video_size_mb=1,
            discord_auto_quality_reduction=True,
        )

        # Stand in for the CRF ladder's output.
        self.reencoded = Path(self._tmp.name) / ".discord_encode" / "discord_crf32.mp4"
        self.reencoded.parent.mkdir()
        self.reencoded.write_bytes(b"SMALL")
        self.app._reencode_for_discord = mock.MagicMock(return_value=self.reencoded)

    def _upload_and_capture_body(self):
        with mock.patch.object(gui_app.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = mock.MagicMock()
            ok = self.app._send_discord_webhook(self.video, "2026-07-25")
        self.assertTrue(ok, self.app.log_message.call_args_list)
        return urlopen.call_args.args[0].data

    def test_reencoded_upload_uses_the_render_name(self):
        body = self._upload_and_capture_body()
        self.assertIn(b'filename="timelapse-2026-07-25.mp4"', body)
        self.assertNotIn(b"discord_crf32.mp4", body)
        self.assertIn(b"SMALL", body)  # still the re-encoded bytes

    def test_suffix_follows_the_bytes_actually_sent(self):
        """A .webm render re-encoded to .mp4 must not be labelled .webm."""
        webm = Path(self._tmp.name) / "timelapse-2026-07-25.webm"
        webm.write_bytes(b"\x00" * (2 * 1024 * 1024))
        self.video = webm
        body = self._upload_and_capture_body()
        self.assertIn(b'filename="timelapse-2026-07-25.mp4"', body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
