"""
Unit tests for the Folder Rollover Hour spinbox wiring in gui_app.py
(update_config_from_ui) - the parse is guarded and clamped so a half-typed
spinbox value can't abort the tab-change auto-save or corrupt the config.

Same approach as test_scheduled_capture.py: a MagicMock stands in for the
GUI instance, so no Tk root is needed.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gui_app import RTSPTimelapseGUI  # noqa: E402


def _fake_gui(spinbox_value, prior=12):
    """A MagicMock GUI with just enough widgets for update_config_from_ui."""
    g = mock.MagicMock()
    g.start_mode_var.get.return_value = "at_time"
    for widget, value in (
        ("ip_entry", "192.168.0.101"),
        ("username_entry", "admin"),
        ("password_entry", "pw"),
        ("stream_path_entry", "/stream1"),
        ("start_time_entry", "22:40"),
        ("end_time_entry", "07:00"),
        ("interval_entry", "30"),
        ("output_entry", "snapshots"),
        ("jpeg_quality_entry", "95"),
        ("proactive_reconnect_entry", "300"),
        ("rollover_hour_spinbox", spinbox_value),
    ):
        getattr(g, widget).get.return_value = value
    g.config_manager.schedule.folder_rollover_hour = prior
    return g


class RolloverHourConfigTests(unittest.TestCase):
    def _update(self, g):
        RTSPTimelapseGUI.update_config_from_ui(g)

    def test_valid_value_saved(self):
        g = _fake_gui("7")
        self._update(g)
        self.assertEqual(g.config_manager.schedule.folder_rollover_hour, 7)

    def test_junk_keeps_prior_value(self):
        g = _fake_gui("junk", prior=12)
        self._update(g)
        self.assertEqual(g.config_manager.schedule.folder_rollover_hour, 12)

    def test_out_of_range_clamped_high(self):
        g = _fake_gui("99")
        self._update(g)
        self.assertEqual(g.config_manager.schedule.folder_rollover_hour, 23)

    def test_negative_clamped_to_zero(self):
        g = _fake_gui("-3")
        self._update(g)
        self.assertEqual(g.config_manager.schedule.folder_rollover_hour, 0)


if __name__ == "__main__":
    unittest.main()
