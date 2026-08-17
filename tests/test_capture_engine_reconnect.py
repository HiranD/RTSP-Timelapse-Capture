"""
Unit tests for the CaptureEngine outage-retry loop (_reconnect_until).

Pins the fix for the night of 2026-07-27: a camera-stream failure made the old
code give up after 3 quick attempts (ERROR state), silently ending an overnight
session hours early. The engine must now keep retrying with backoff until the
user stops it or the schedule window ends - and neither of those exits may be
reported as ERROR, because the GUI treats ERROR as "tear the session down".

No camera and no cv2: _open_capture is monkeypatched, and the module-level
_RECONNECT_BACKOFF is patched down to milliseconds.
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config_manager import ConfigManager  # noqa: E402
from capture_engine import CaptureEngine, CaptureState  # noqa: E402


def _engine():
    cfg = ConfigManager().to_dict()
    cfg["schedule"]["ignore_window"] = True
    return CaptureEngine(cfg)


FAST_BACKOFF = mock.patch("capture_engine._RECONNECT_BACKOFF", (0.01,))


class ReconnectUntilTests(unittest.TestCase):
    def test_retries_until_success(self):
        eng = _engine()
        fake_cap = mock.Mock()
        eng._open_capture = mock.Mock(side_effect=[None, None, fake_cap])
        with FAST_BACKOFF:
            ok = eng._reconnect_until("rtsp://x", datetime.max)
        self.assertTrue(ok)
        self.assertIs(eng.cap, fake_cap)
        self.assertEqual(eng.state, CaptureState.RUNNING)
        self.assertEqual(eng._open_capture.call_count, 3)

    def test_connection_start_time_reset_on_success(self):
        # Stale connection_start_time would make the proactive-reconnect check
        # fire immediately after a long outage.
        eng = _engine()
        eng.connection_start_time = datetime.now() - timedelta(hours=3)
        eng._open_capture = mock.Mock(return_value=mock.Mock())
        with FAST_BACKOFF:
            self.assertTrue(eng._reconnect_until("rtsp://x", datetime.max))
        age = (datetime.now() - eng.connection_start_time).total_seconds()
        self.assertLess(age, 5)

    def test_stop_event_ends_retry_without_error(self):
        eng = _engine()

        def fail_and_stop(*args, **kwargs):
            eng.stop_event.set()
            return None

        eng._open_capture = mock.Mock(side_effect=fail_and_stop)
        with FAST_BACKOFF:
            ok = eng._reconnect_until("rtsp://x", datetime.max)
        self.assertFalse(ok)
        self.assertNotEqual(eng.state, CaptureState.ERROR)

    def test_end_dt_reached_returns_false_without_error(self):
        eng = _engine()
        eng._open_capture = mock.Mock(return_value=None)
        end_dt = datetime.now() + timedelta(milliseconds=50)
        with FAST_BACKOFF:
            ok = eng._reconnect_until("rtsp://x", end_dt)
        self.assertFalse(ok)
        self.assertNotEqual(eng.state, CaptureState.ERROR)

    def test_state_goes_reconnecting_then_running(self):
        eng = _engine()
        states = []
        eng.set_status_callback(lambda state, stats: states.append(state))
        eng._open_capture = mock.Mock(side_effect=[None, mock.Mock()])
        with FAST_BACKOFF:
            self.assertTrue(eng._reconnect_until("rtsp://x", datetime.max))
        self.assertIn(CaptureState.RECONNECTING, states)
        self.assertLess(states.index(CaptureState.RECONNECTING),
                        states.index(CaptureState.RUNNING))

    def test_outage_counted_once_not_per_attempt(self):
        eng = _engine()
        eng._open_capture = mock.Mock(side_effect=[None, None, None, mock.Mock()])
        with FAST_BACKOFF:
            self.assertTrue(eng._reconnect_until("rtsp://x", datetime.max))
        self.assertEqual(eng.disconnect_count, 1)


class InitialConnectFailureTests(unittest.TestCase):
    """A camera that is down at session start must enter the retry loop, not ERROR."""

    def test_initial_connect_failure_routes_to_reconnect_until(self):
        eng = _engine()
        states = []
        eng.set_status_callback(lambda state, stats: states.append(state))
        eng._open_capture = mock.Mock(return_value=None)

        def stop_and_fail(url, end_dt):
            eng.stop_event.set()
            return False

        eng._reconnect_until = mock.Mock(side_effect=stop_and_fail)
        eng._capture_loop()

        eng._reconnect_until.assert_called_once()
        self.assertEqual(eng._reconnect_until.call_args[0][1], datetime.max)
        self.assertEqual(eng.state, CaptureState.STOPPED)
        self.assertNotIn(CaptureState.ERROR, states)

    def test_stop_during_initial_burst_skips_retry_loop(self):
        # _open_capture returns None for "stop requested" too; that must not be
        # booked as an outage.
        eng = _engine()
        eng.stop_event.set()
        eng._open_capture = mock.Mock(return_value=None)
        eng._reconnect_until = mock.Mock()
        eng._capture_loop()
        eng._reconnect_until.assert_not_called()
        self.assertEqual(eng.disconnect_count, 0)


if __name__ == "__main__":
    unittest.main()
