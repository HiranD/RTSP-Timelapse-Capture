"""
Unit tests for RTSPBufferlessCapture.release() handing teardown to the reader.

Pins the fix for the 2026-09-03 / 2026-09-05 crashes: release() used to call
cv2.VideoCapture.release() while the reader thread could still be inside
cap.read() on the same handle - a use-after-free in OpenCV's FFmpeg backend
that killed the app with no Python traceback. The handle must now be released
exactly once, and never from a thread other than the one that may be reading.

cv2.VideoCapture is replaced by a small fake; no camera involved.
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import capture_engine  # noqa: E402
from capture_engine import RTSPBufferlessCapture  # noqa: E402

FAST_JOIN = mock.patch("capture_engine._RELEASE_JOIN_TIMEOUT", 0.2)


class _FakeCap:
    """Stand-in cv2.VideoCapture. read() blocks until `unblock` is set (a
    stalled stream) unless `blocking` is False; release() records the calling
    thread's name so tests can assert WHO tore the handle down."""

    def __init__(self, blocking=True, raise_on_read=False):
        self.unblock = threading.Event()
        self.blocking = blocking
        self.raise_on_read = raise_on_read
        self.release_calls = []
        self._opened = True

    def isOpened(self):
        return self._opened

    def set(self, prop, value):
        return True

    def read(self):
        if self.raise_on_read:
            raise RuntimeError("decoder blew up")
        if self.blocking:
            self.unblock.wait()
        return False, None

    def release(self):
        self.release_calls.append(threading.current_thread().name)
        self._opened = False


def _capture(fake):
    with mock.patch.object(capture_engine.cv2, "VideoCapture", return_value=fake):
        return RTSPBufferlessCapture("rtsp://x")


class ReaderOwnedReleaseTests(unittest.TestCase):
    def test_blocked_reader_defers_release_to_the_reader(self):
        fake = _FakeCap(blocking=True)
        cap = _capture(fake)

        with FAST_JOIN:
            started = time.time()
            cap.release()
        # Returned promptly (join timeout, not the stall) and did NOT touch the
        # handle while the reader was still inside read().
        self.assertLess(time.time() - started, 1.5)
        self.assertEqual(fake.release_calls, [])
        self.assertTrue(cap.thread.is_alive())

        # The stalled read returns: the reader releases, exactly once, itself.
        fake.unblock.set()
        cap.thread.join(timeout=2.0)
        self.assertFalse(cap.thread.is_alive())
        self.assertEqual(fake.release_calls, ["rtsp-reader"])

    def test_idle_reader_releases_exactly_once(self):
        fake = _FakeCap(blocking=False)  # read() returns immediately
        cap = _capture(fake)
        cap.release()
        cap.thread.join(timeout=2.0)
        self.assertEqual(len(fake.release_calls), 1)

    def test_release_is_idempotent(self):
        fake = _FakeCap(blocking=False)
        cap = _capture(fake)
        cap.release()
        cap.release()
        cap.thread.join(timeout=2.0)
        self.assertEqual(len(fake.release_calls), 1)

    def test_read_after_release_returns_nothing(self):
        fake = _FakeCap(blocking=False)
        cap = _capture(fake)
        cap.release()
        self.assertEqual(cap.read(timeout=0.1), (False, None))
        self.assertFalse(cap.isOpened())

    def test_reader_exception_still_releases_the_handle(self):
        """A reader that dies on an exception must not strand the handle."""
        fake = _FakeCap(raise_on_read=True)
        # The exception is the point here, not a failure: route it to a mock
        # hook so the suite output doesn't show a traceback that reads like
        # one - and so we can assert it really surfaced.
        with mock.patch("threading.excepthook") as hook:
            cap = _capture(fake)
            cap.thread.join(timeout=2.0)
        self.assertFalse(cap.thread.is_alive())
        hook.assert_called_once()
        self.assertEqual(fake.release_calls, ["rtsp-reader"])
        cap.release()  # and the caller-side release stays a no-op
        self.assertEqual(len(fake.release_calls), 1)


if __name__ == "__main__":
    unittest.main()
