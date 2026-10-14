"""
Unit tests for the background-thread -> Tk hand-off in gui_app.py
(_post_to_ui / _pump_ui_calls / _run_on_ui).

The remote API serves every request on a new thread. When those threads called
root.after() themselves, Tcl allocated per-thread state that was never freed:
~17 KB and one handle per request, which grew the test rig to 11 GB over three
weeks of NINA dock-panel polling. These tests pin the fix: background threads
only queue work, and every Tk call happens on the main thread.
"""

import ctypes
import queue
import sys
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import gui_app  # noqa: E402
from gui_app import RTSPTimelapseGUI  # noqa: E402


def _bare_gui(root):
    """An RTSPTimelapseGUI with only the hand-off state that __init__ sets up."""
    g = RTSPTimelapseGUI.__new__(RTSPTimelapseGUI)
    g.root = root
    g._ui_calls = queue.SimpleQueue()
    return g


class _RecordingRoot:
    """Stands in for the Tk root and records which thread called after()."""

    def __init__(self):
        self.after_threads = []

    def after(self, ms, func):
        self.after_threads.append(threading.current_thread())


class PumpTests(unittest.TestCase):
    def test_runs_queued_calls_in_order_and_rearms(self):
        root = mock.Mock()
        g = _bare_gui(root)
        order = []
        g._post_to_ui(lambda: order.append(1))
        g._post_to_ui(lambda: order.append(2))

        g._pump_ui_calls()

        self.assertEqual(order, [1, 2])
        root.after.assert_called_once_with(gui_app._UI_PUMP_MS, g._pump_ui_calls)

    def test_failing_call_does_not_stop_the_pump(self):
        root = mock.Mock()
        g = _bare_gui(root)
        ran = []

        def boom():
            raise RuntimeError("boom")

        g._post_to_ui(boom)
        g._post_to_ui(lambda: ran.append(True))

        with self.assertLogs("rtsp.app", level="ERROR"):
            g._pump_ui_calls()

        self.assertEqual(ran, [True])  # the call after the failure still ran
        root.after.assert_called_once()  # and the pump re-armed

    def test_destroyed_window_stops_pumping_quietly(self):
        root = mock.Mock()
        root.after.side_effect = tk.TclError("application has been destroyed")
        g = _bare_gui(root)

        g._pump_ui_calls()  # must not raise

    def test_run_on_ui_never_touches_tk_off_the_main_thread(self):
        root = _RecordingRoot()
        g = _bare_gui(root)
        results = []
        workers = [threading.Thread(target=lambda i=i: results.append(g._run_on_ui(lambda: i * 2)))
                   for i in range(20)]
        for t in workers:
            t.start()

        deadline = time.monotonic() + 10
        while any(t.is_alive() for t in workers) and time.monotonic() < deadline:
            g._pump_ui_calls()  # this test is the "main loop"
            time.sleep(0.001)
        for t in workers:
            t.join(1)

        self.assertEqual(sorted(results), [i * 2 for i in range(20)])
        self.assertTrue(root.after_threads)
        self.assertTrue(all(t is threading.main_thread() for t in root.after_threads))

    def test_log_message_off_the_main_thread_is_queued(self):
        g = _bare_gui(mock.Mock())
        g._file_logger = mock.Mock()
        g.log_text = mock.Mock()

        t = threading.Thread(target=lambda: g.log_message("INFO", "from a worker"))
        t.start()
        t.join()

        g.log_text.insert.assert_not_called()  # nothing touched Tk on the worker
        g.root.after.assert_not_called()
        g._pump_ui_calls()
        g.log_text.insert.assert_called_once()
        self.assertIn("from a worker", g.log_text.insert.call_args.args[1])


@unittest.skipUnless(sys.platform == "win32", "handle counting is Windows-only")
class HandleLeakTests(unittest.TestCase):
    """The original symptom, measured: one leaked handle per thread that called Tk."""

    THREADS = 500

    @staticmethod
    def _handle_count():
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        count = ctypes.c_ulong()
        k32.GetProcessHandleCount(k32.GetCurrentProcess(), ctypes.byref(count))
        return count.value

    def test_run_on_ui_from_many_new_threads_does_not_leak_handles(self):
        try:
            root = tk.Tk()
        except tk.TclError as e:
            self.skipTest(f"no Tk display: {e}")
        root.withdraw()
        self.addCleanup(root.destroy)
        g = _bare_gui(root)
        g._pump_ui_calls()
        measured = {}

        def burst(n):
            workers = [threading.Thread(target=lambda: g._run_on_ui(lambda: None))
                       for _ in range(n)]
            for t in workers:
                t.start()
            for t in workers:
                t.join(30)

        def driver():
            try:
                burst(20)  # warm-up: one-off allocations shouldn't count
                before = self._handle_count()
                burst(self.THREADS)
                measured["leaked"] = self._handle_count() - before
            finally:
                g._post_to_ui(root.quit)

        # A real mainloop, as in the app: Tk only serves calls from other threads
        # while the main thread sits in mainloop(), so update() polling can't stand in.
        threading.Thread(target=driver, daemon=True).start()
        root.mainloop()

        # Calling root.after() from each thread leaked one handle per thread (+500).
        # The wide margin absorbs handles that other tests' leftover threads open or
        # close while this runs inside the full suite.
        self.assertLess(measured["leaked"], self.THREADS // 4)


if __name__ == "__main__":
    unittest.main()
