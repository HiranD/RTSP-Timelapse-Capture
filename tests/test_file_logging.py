"""
Unit tests for the opt-in diagnostic file logging (PR #22).

Covers the security-sensitive app_logging helpers (mask_secrets must never let
a camera/MQTT password reach a log file people send around) and the
_set_file_logging attach/detach/re-adopt lifecycle - the re-adopt path already
needed one follow-up fix (a re-created GUI kept the handler but left the logger
at WARNING, silently dropping all DEBUG detail).

_set_file_logging is exercised unbound on a stub "self": it only touches
_file_logger / _file_log_handler and get_app_base_dir(), so no Tk window is
needed.
"""

import logging
import logging.handlers
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from app_logging import get_logger, mask_secrets, trunc  # noqa: E402
import gui_app  # noqa: E402


class MaskSecretsTests(unittest.TestCase):
    def test_masks_password_keys_at_any_depth(self):
        config = {
            "camera": {"password": "secret", "ip_address": "1.2.3.4"},
            "astro_schedule": {"mqtt_password": "broker-pw", "mqtt_username": "user"},
        }
        masked = mask_secrets(config)
        self.assertEqual(masked["camera"]["password"], "****")
        self.assertEqual(masked["astro_schedule"]["mqtt_password"], "****")
        # Non-secret values pass through untouched.
        self.assertEqual(masked["camera"]["ip_address"], "1.2.3.4")
        self.assertEqual(masked["astro_schedule"]["mqtt_username"], "user")

    def test_original_is_not_mutated(self):
        config = {"camera": {"password": "secret"}}
        mask_secrets(config)
        self.assertEqual(config["camera"]["password"], "secret")

    def test_empty_password_stays_empty(self):
        # "" must not become "****" - that would misreport whether one is set.
        self.assertEqual(mask_secrets({"password": ""}), {"password": ""})

    def test_lists_are_traversed(self):
        value = [{"password": "x"}, "plain"]
        self.assertEqual(mask_secrets(value), [{"password": "****"}, "plain"])

    def test_no_password_survives_a_full_config_dump(self):
        # The exact pattern gui_app logs at capture start.
        from config_manager import ConfigManager
        manager = ConfigManager()
        manager.camera.password = "cam-secret"
        manager.astro_schedule.mqtt_password = "mqtt-secret"
        dumped = repr(mask_secrets(manager.to_dict()))
        self.assertNotIn("cam-secret", dumped)
        self.assertNotIn("mqtt-secret", dumped)


class TruncTests(unittest.TestCase):
    def test_short_value_passes_through(self):
        self.assertEqual(trunc({"a": 1}), repr({"a": 1}))

    def test_long_value_is_capped(self):
        result = trunc("x" * 5000, limit=100)
        self.assertLess(len(result), 200)
        self.assertIn("chars)", result)


class _StubGui(types.SimpleNamespace):
    """Just the attributes _set_file_logging touches."""


def _make_stub():
    logger = get_logger()
    stub = _StubGui(_file_logger=logger, _file_log_handler=None)
    return stub, logger


class SetFileLoggingTests(unittest.TestCase):
    """Lifecycle of the rotating handler behind the Integrations checkbox."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(
            gui_app, "get_app_base_dir", return_value=Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        # The "rtsp" logger is process-global: start each test from the app's
        # startup state and restore it afterwards so other tests aren't affected.
        self.logger = get_logger()
        self._reset_logger()
        self.addCleanup(self._reset_logger)

    def _reset_logger(self):
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            handler.close()
        self.logger.addHandler(logging.NullHandler())
        self.logger.setLevel(logging.WARNING)

    def _file_handlers(self):
        return [h for h in self.logger.handlers
                if isinstance(h, logging.handlers.RotatingFileHandler)]

    def test_enable_attaches_handler_and_raises_level(self):
        stub, logger = _make_stub()
        ok, err = gui_app.RTSPTimelapseGUI._set_file_logging(stub, True)
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(len(self._file_handlers()), 1)
        self.assertTrue(logger.isEnabledFor(logging.DEBUG))
        # The startup line is emitted on attach, so the file exists already.
        self.assertTrue((Path(self.tmp.name) / "logs" / "app.log").exists())

    def test_enable_is_idempotent(self):
        stub, _ = _make_stub()
        gui_app.RTSPTimelapseGUI._set_file_logging(stub, True)
        ok, err = gui_app.RTSPTimelapseGUI._set_file_logging(stub, True)
        self.assertTrue(ok)
        self.assertEqual(len(self._file_handlers()), 1)

    def test_disable_removes_handler_and_lowers_level(self):
        stub, logger = _make_stub()
        gui_app.RTSPTimelapseGUI._set_file_logging(stub, True)
        ok, _ = gui_app.RTSPTimelapseGUI._set_file_logging(stub, False)
        self.assertTrue(ok)
        self.assertEqual(self._file_handlers(), [])
        self.assertIsNone(stub._file_log_handler)
        self.assertFalse(logger.isEnabledFor(logging.DEBUG))

    def test_readopted_handler_still_raises_level(self):
        # Pins the PR #22 review fix: a re-created GUI adopts the process-wide
        # handler after __init__ reset the logger to WARNING; enabling must
        # still raise the level or all DEBUG detail silently stops.
        first, _ = _make_stub()
        gui_app.RTSPTimelapseGUI._set_file_logging(first, True)

        # Second instance: __init__'s sequence - reset to WARNING, adopt handler.
        self.logger.setLevel(logging.WARNING)
        second = _StubGui(_file_logger=self.logger,
                          _file_log_handler=self._file_handlers()[0])
        ok, _ = gui_app.RTSPTimelapseGUI._set_file_logging(second, True)
        self.assertTrue(ok)
        self.assertEqual(len(self._file_handlers()), 1)  # no duplicate
        self.assertTrue(self.logger.isEnabledFor(logging.DEBUG))

    def test_unwritable_log_dir_fails_cleanly(self):
        stub, logger = _make_stub()
        # A file where the logs *directory* should be makes mkdir raise.
        (Path(self.tmp.name) / "logs").write_text("not a directory")
        ok, err = gui_app.RTSPTimelapseGUI._set_file_logging(stub, True)
        self.assertFalse(ok)
        self.assertTrue(err)
        self.assertEqual(self._file_handlers(), [])
        self.assertFalse(logger.isEnabledFor(logging.DEBUG))


if __name__ == "__main__":
    unittest.main()
