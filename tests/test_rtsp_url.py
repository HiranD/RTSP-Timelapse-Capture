"""
Unit tests for CaptureEngine._build_rtsp_url() - issue #16.

The configured camera.stream_path used to be ignored: the URL was built with a
hardcoded "/stream1", so every camera that serves a different path (Hikvision,
Dahua, UniFi) failed to connect. These tests pin the path down - taken verbatim,
query strings intact, no "?tcp" suffix - without needing a camera or a network.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config_manager import ConfigManager  # noqa: E402
from capture_engine import CaptureEngine  # noqa: E402


def _engine(ip="192.168.0.101", username="admin", password="pw", **camera):
    """Build an engine whose camera section can be tweaked per test.

    Pass stream_path=None to drop the key entirely (simulates a config written
    by an older version that never had the field).
    """
    cfg = ConfigManager().to_dict()
    cfg["camera"]["ip_address"] = ip
    cfg["camera"]["username"] = username
    cfg["camera"]["password"] = password
    for key, value in camera.items():
        if value is None:
            cfg["camera"].pop(key, None)
        else:
            cfg["camera"][key] = value
    return CaptureEngine(cfg)


class BuildRtspUrlTests(unittest.TestCase):
    def test_default_stream1_path(self):
        # The historical behavior for /stream1 cameras must not change.
        eng = _engine(stream_path="/stream1")
        self.assertEqual(eng._build_rtsp_url(), "rtsp://admin:pw@192.168.0.101/stream1")

    def test_dahua_query_string_preserved(self):
        # The query string must survive verbatim - this is what issue #16 broke.
        eng = _engine(stream_path="/cam/realmonitor?channel=1&subtype=0")
        url = eng._build_rtsp_url()
        self.assertEqual(url, "rtsp://admin:pw@192.168.0.101/cam/realmonitor?channel=1&subtype=0")
        self.assertNotIn("?tcp", url)

    def test_hikvision_path_honored(self):
        eng = _engine(stream_path="/Streaming/Channels/101")
        self.assertEqual(eng._build_rtsp_url(), "rtsp://admin:pw@192.168.0.101/Streaming/Channels/101")

    def test_missing_leading_slash_is_repaired(self):
        eng = _engine(stream_path="stream1")
        self.assertEqual(eng._build_rtsp_url(), "rtsp://admin:pw@192.168.0.101/stream1")

    def test_empty_path_falls_back_to_default(self):
        eng = _engine(stream_path="")
        self.assertEqual(eng._build_rtsp_url(), "rtsp://admin:pw@192.168.0.101/stream1")

    def test_whitespace_only_path_falls_back_to_default(self):
        eng = _engine(stream_path="   ")
        self.assertEqual(eng._build_rtsp_url(), "rtsp://admin:pw@192.168.0.101/stream1")

    def test_absent_key_falls_back_to_default(self):
        # A config dict without the key at all must not raise KeyError.
        eng = _engine(stream_path=None)
        self.assertNotIn("stream_path", eng.config["camera"])
        self.assertEqual(eng._build_rtsp_url(), "rtsp://admin:pw@192.168.0.101/stream1")

    def test_custom_port_preserved(self):
        # ip_address doubles as host:port; it passes through untouched.
        eng = _engine(ip="85.0.0.234:1554", stream_path="/stream1")
        self.assertEqual(eng._build_rtsp_url(), "rtsp://admin:pw@85.0.0.234:1554/stream1")

    def test_issue_16_reporter_config(self):
        # The regression anchor: the reporter's exact settings must reproduce the
        # URL that worked for them in VLC.
        eng = _engine(
            ip="85.0.0.234:1554",
            username="admin",
            password="pw",
            stream_path="/cam/realmonitor?channel=1&subtype=0",
        )
        self.assertEqual(
            eng._build_rtsp_url(),
            "rtsp://admin:pw@85.0.0.234:1554/cam/realmonitor?channel=1&subtype=0",
        )


class SanitizeUrlTests(unittest.TestCase):
    def test_password_is_masked(self):
        # The URL is logged now, and users paste logs into issue reports.
        eng = _engine(password="s3cr3t", stream_path="/stream1")
        sanitized = eng._sanitize_url(eng._build_rtsp_url())
        self.assertNotIn("s3cr3t", sanitized)
        self.assertEqual(sanitized, "rtsp://admin:****@192.168.0.101/stream1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
