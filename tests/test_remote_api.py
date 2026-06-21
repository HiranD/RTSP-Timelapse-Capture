"""
Unit tests for src/remote_api.py (the localhost Remote Control HTTP API).

The server is started on an ephemeral port (port=0) with mock callbacks, then
exercised over real HTTP via urllib. No GUI / Tkinter is involved here - the
server is Tk-agnostic by design.
"""

import json
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from remote_api import RemoteControlServer  # noqa: E402


class RemoteApiTests(unittest.TestCase):
    def setUp(self):
        self.on_start = mock.Mock(return_value=(True, None))
        self.on_stop = mock.Mock(return_value=(True, None))
        self.on_create_video = mock.Mock(
            return_value=(True, "video creation started for 20250620", 202, "20250620")
        )
        self.get_status = mock.Mock(return_value={
            "capturing": False, "state": "Stopped", "frame_count": 0,
            "failed_frame_count": 0, "uptime_seconds": 0, "last_error": None,
            "scheduler_enabled": False,
        })

        self.server = RemoteControlServer(
            on_start=self.on_start,
            on_stop=self.on_stop,
            on_create_video=self.on_create_video,
            get_status=self.get_status,
            version="9.9.9",
            host="127.0.0.1",
            port=0,  # ephemeral - real port read back from .port
        )
        self.server.start()
        self.base = f"http://127.0.0.1:{self.server.port}"
        self.addCleanup(self.server.stop)

    # ----------------------------------------------------------------- helper

    def _request(self, path, method="GET", body=None, headers=None):
        """Return (status_code, parsed_json) for a request to the test server."""
        data = None
        hdrs = dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    # ------------------------------------------------------------------ tests

    def test_health(self):
        code, payload = self._request("/health")
        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["version"], "9.9.9")

    def test_status_shape(self):
        code, payload = self._request("/status")
        self.assertEqual(code, 200)
        self.assertIn("capturing", payload)
        self.assertIn("scheduler_enabled", payload)
        self.get_status.assert_called()

    def test_start_calls_callback(self):
        code, payload = self._request("/capture/start", method="POST")
        self.assertEqual(code, 202)
        self.assertEqual(payload["status"], "starting")
        self.on_start.assert_called_once()

    def test_stop_calls_callback(self):
        code, payload = self._request("/capture/stop", method="POST")
        self.assertEqual(code, 200)
        self.assertEqual(payload["status"], "stopping")
        self.on_stop.assert_called_once()

    def test_start_failure_returns_400(self):
        self.on_start.return_value = (False, "Invalid configuration")
        code, payload = self._request("/capture/start", method="POST")
        self.assertEqual(code, 400)
        self.assertEqual(payload["error"], "Invalid configuration")

    def test_video_default_date(self):
        code, payload = self._request("/video/create", method="POST")
        self.assertEqual(code, 202)
        self.on_create_video.assert_called_once_with(None, None)
        # No body sent, but the response echoes the resolved date, not null.
        self.assertEqual(payload["date"], "20250620")

    def test_video_explicit_date(self):
        code, payload = self._request("/video/create", method="POST", body={"date": "20250620"})
        self.assertEqual(code, 202)
        self.on_create_video.assert_called_once_with("20250620", None)
        self.assertEqual(payload["date"], "20250620")

    def test_video_with_since(self):
        # `since` (YYYYMMDD-HHMMSS) is parsed from the body and forwarded so the
        # app can render only frames from one session in a shared date folder.
        code, payload = self._request(
            "/video/create", method="POST", body={"since": "20250620-210000"})
        self.assertEqual(code, 202)
        self.on_create_video.assert_called_once_with(None, "20250620-210000")
        self.assertEqual(payload["since"], "20250620-210000")

    def test_video_missing_folder_404(self):
        self.on_create_video.return_value = (False, "no snapshots for 20200101", 404, "20200101")
        code, payload = self._request("/video/create", method="POST", body={"date": "20200101"})
        self.assertEqual(code, 404)
        self.assertIn("error", payload)

    def test_unknown_path_404(self):
        code, payload = self._request("/does-not-exist")
        self.assertEqual(code, 404)

    def test_wrong_method_405(self):
        # /capture/start is POST-only; a GET should be 405, not 404.
        code, payload = self._request("/capture/start", method="GET")
        self.assertEqual(code, 405)

    def test_non_local_host_403(self):
        # DNS-rebinding / CSRF guard: a non-loopback Host header is rejected.
        code, payload = self._request("/status", headers={"Host": "evil.example.com"})
        self.assertEqual(code, 403)
        self.on_start.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
