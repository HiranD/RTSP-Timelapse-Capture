"""
Unit tests for src/startup_manager.py

`winreg` is mocked (injected into sys.modules), so these tests run on any
platform and never touch the real registry.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import startup_manager  # noqa: E402


def _fake_winreg():
    """A MagicMock standing in for the winreg module.

    MagicMock supports the context-manager protocol, so
    `with winreg.OpenKey(...) as key:` works out of the box. Constants are
    just attributes; tests set side effects on the call methods as needed.
    """
    return mock.MagicMock(name="winreg")


class IsEnabledTests(unittest.TestCase):
    def setUp(self):
        self.supported = mock.patch.object(
            startup_manager, "is_supported", return_value=True
        )
        self.supported.start()
        self.addCleanup(self.supported.stop)

    def test_value_present_returns_true(self):
        fake = _fake_winreg()  # QueryValueEx does not raise -> enabled
        with mock.patch.dict(sys.modules, {"winreg": fake}):
            self.assertTrue(startup_manager.is_enabled())

    def test_missing_run_key_returns_false(self):
        # The whole Run key is absent -> OpenKey raises.
        fake = _fake_winreg()
        fake.OpenKey.side_effect = FileNotFoundError
        with mock.patch.dict(sys.modules, {"winreg": fake}):
            self.assertFalse(startup_manager.is_enabled())

    def test_key_present_but_value_absent_returns_false(self):
        # Run key exists but our value hasn't been written -> QueryValueEx raises.
        fake = _fake_winreg()
        fake.QueryValueEx.side_effect = FileNotFoundError
        with mock.patch.dict(sys.modules, {"winreg": fake}):
            self.assertFalse(startup_manager.is_enabled())

    def test_oserror_returns_false(self):
        fake = _fake_winreg()
        fake.OpenKey.side_effect = OSError
        with mock.patch.dict(sys.modules, {"winreg": fake}):
            self.assertFalse(startup_manager.is_enabled())

    def test_unsupported_platform_returns_false(self):
        with mock.patch.object(startup_manager, "is_supported", return_value=False):
            self.assertFalse(startup_manager.is_enabled())


class EnableDisableTests(unittest.TestCase):
    def setUp(self):
        self.supported = mock.patch.object(
            startup_manager, "is_supported", return_value=True
        )
        self.supported.start()
        self.addCleanup(self.supported.stop)

    def test_enable_success(self):
        fake = _fake_winreg()
        with mock.patch.dict(sys.modules, {"winreg": fake}), \
             mock.patch.object(startup_manager, "_launch_command", return_value='"app.exe"'):
            ok, msg = startup_manager.enable()
        self.assertTrue(ok)
        fake.SetValueEx.assert_called_once()

    def test_enable_missing_launcher_is_caught(self):
        # _launch_command raises FileNotFoundError (an OSError subclass);
        # enable() must catch it and report failure rather than crash.
        fake = _fake_winreg()
        with mock.patch.dict(sys.modules, {"winreg": fake}), \
             mock.patch.object(startup_manager, "_launch_command",
                               side_effect=FileNotFoundError("no launcher")):
            ok, msg = startup_manager.enable()
        self.assertFalse(ok)
        self.assertIn("Could not enable", msg)
        fake.SetValueEx.assert_not_called()

    def test_disable_success(self):
        fake = _fake_winreg()
        with mock.patch.dict(sys.modules, {"winreg": fake}):
            ok, msg = startup_manager.disable()
        self.assertTrue(ok)
        fake.DeleteValue.assert_called_once()

    def test_disable_already_absent_is_success(self):
        fake = _fake_winreg()
        fake.DeleteValue.side_effect = FileNotFoundError
        with mock.patch.dict(sys.modules, {"winreg": fake}):
            ok, msg = startup_manager.disable()
        self.assertTrue(ok)  # desired end state already reached

    def test_unsupported_platform_no_ops(self):
        with mock.patch.object(startup_manager, "is_supported", return_value=False):
            ok_enable, _ = startup_manager.enable()
            ok_disable, _ = startup_manager.disable()
        self.assertFalse(ok_enable)
        self.assertFalse(ok_disable)


class LaunchCommandTests(unittest.TestCase):
    def test_frozen_uses_executable_path(self):
        with mock.patch.object(startup_manager.sys, "frozen", True, create=True), \
             mock.patch.object(startup_manager.sys, "executable", r"C:\app\RTSP_Timelapse.exe"):
            cmd = startup_manager._launch_command()
        self.assertEqual(cmd, '"C:\\app\\RTSP_Timelapse.exe"')

    def test_source_includes_launcher(self):
        # Not frozen: command should reference run_gui.py (which exists in repo).
        with mock.patch.object(startup_manager.sys, "frozen", False, create=True):
            cmd = startup_manager._launch_command()
        self.assertIn("run_gui.py", cmd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
