"""
Regression tests: every app module is loaded exactly once, under its bare name.

Twelve modules used to import shared code as `from src.X import ...` with a bare
`from X import ...` fallback, while gui_app imported bare. With the repo root on
sys.path - which run_gui.py, `python -m unittest` from the repo root, and
PyInstaller's analysis all arrange - BOTH names resolve, so each of those modules
was loaded twice. capture_history's singleton therefore existed twice: gui_app
recorded manual/NINA sessions into one copy while scheduling_panel and the
calendar used the other, and each copy's save overwrote the other's file. On the
rig this showed as captured nights staying gray until a restart (2026-09-12).

Both sys.path entries are set up here on purpose: a `src.`-qualified import must
be *possible* for the assertions below to mean anything.
"""

import importlib.util
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))  # arms the trap: `import src.X` now resolves

# Everything the running app imports, bare - gui_app pulls in the rest.
import capture_history  # noqa: E402
import calendar_widget  # noqa: E402
import gui_app  # noqa: E402
import scheduling_panel  # noqa: E402
import integrations_panel  # noqa: E402,F401
import remote_api  # noqa: E402,F401
import event_log  # noqa: E402,F401
import ffmpeg_wrapper  # noqa: E402,F401
import preset_manager  # noqa: E402,F401
import astro_scheduler  # noqa: E402,F401
import startup_manager  # noqa: E402,F401


class SingleCopyTests(unittest.TestCase):
    def test_no_src_qualified_modules_after_importing_the_app(self):
        # Preconditions: the trap is real - src is a package and importable here.
        self.assertTrue((_ROOT / "src" / "__init__.py").exists())
        self.assertIsNotNone(importlib.util.find_spec("src"))

        offenders = sorted(m for m in sys.modules if m == "src" or m.startswith("src."))
        self.assertEqual(offenders, [],
                         f"modules loaded a second time under the src. name: {offenders}")


class SharedHistoryTests(unittest.TestCase):
    """The recorder (gui_app), the scheduler panel and the calendar must all hold
    the one capture-history singleton."""

    def test_singleton_accessor_is_one_function(self):
        self.assertIs(gui_app.get_capture_history, capture_history.get_capture_history)
        self.assertIs(scheduling_panel.get_capture_history, capture_history.get_capture_history)
        self.assertIs(calendar_widget.get_capture_history, capture_history.get_capture_history)

    def test_session_recorded_by_gui_is_visible_to_the_calendar(self):
        """The user-facing guarantee: a manual/NINA night recorded on stop shows
        on the calendar's next redraw, no restart needed."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        mgr = capture_history.CaptureHistoryManager(config_dir=Path(tmp.name))
        with mock.patch.object(capture_history, "_instance", mgr):
            # What gui_app._record_own_session does on stop...
            gui_app.get_capture_history().record_session(
                "20260909", datetime(2026, 9, 9, 21, 37), datetime(2026, 9, 10, 8, 2),
                1137, source="remote")
            # ...and what the calendar reads for that cell on redraw.
            widget = mock.MagicMock()
            widget.capture_history = calendar_widget.get_capture_history()
            sessions = calendar_widget.TwoMonthCalendar._day_sessions(widget, date(2026, 9, 9))

        self.assertEqual([s.source for s in sessions], ["remote"])
        self.assertTrue(sessions[0].succeeded)


if __name__ == "__main__":
    unittest.main()
