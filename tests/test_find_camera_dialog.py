"""
GUI tests for the Find Camera dialog (gui_app.find_camera) and the camera-MAC
learning behind it, with discover() / lookup_mac() mocked.

Pins the parts that are easy to break:
- the search and the MAC lookup run off the Tk thread and hand back through
  _post_to_ui (a Tk call from those threads would leak Tcl per-thread state);
- the configured camera is recognised by its saved MAC after DHCP moves it, even
  when another device now has its old address;
- Use Selected keeps a custom port and saves address + MAC together;
- a dialog closed mid-search ignores the late result.
"""

import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import gui_app  # noqa: E402
from camera_discovery import DiscoveredCamera  # noqa: E402
from config_manager import ConfigManager  # noqa: E402
from gui_app import RTSPTimelapseGUI  # noqa: E402

OLD_IP, NEW_IP = "192.168.171.22", "192.168.171.35"
MINE, OTHER = "24:48:45:00:00:01", "24:48:45:00:00:02"

CAMERAS = [
    DiscoveredCamera(ip=OLD_IP, mac=MINE, model="I81EM",
                     dhcp=True, activated=True, sources={"SADP", "ONVIF"}),
    DiscoveredCamera(ip="192.168.171.30", model="IPC-HDW2431T", sources={"ONVIF"}),
]


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _bare_gui(root):
    """An RTSPTimelapseGUI with just what find_camera and the MAC learning use.

    The config is a real ConfigManager, but saves are mocked and the config path
    points into a temp dir, so nothing touches the repo's config/app_config.json.
    """
    g = RTSPTimelapseGUI.__new__(RTSPTimelapseGUI)
    g.root = root
    g._ui_calls = queue.SimpleQueue()
    g._mac_lookup_host = None
    g.config_manager = ConfigManager()
    g.config_manager.save_to_file = mock.Mock(return_value=(True, "saved"))
    g.log_message = mock.Mock()
    return g


class _GuiTestCase(unittest.TestCase):

    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("200x100+0+0")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(gui_app, "get_config_path",
                                    return_value=Path(tmp.name) / "config" / "app_config.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.gui = _bare_gui(self.root)

    def tearDown(self):
        self.root.destroy()

    def _drain(self, timeout=5):
        """Wait for a background thread's _post_to_ui call, then run it as
        _pump_ui_calls would (without re-arming an after() that outlives the root)."""
        deadline = time.monotonic() + timeout
        while self.gui._ui_calls.empty():
            self.assertLess(time.monotonic(), deadline, "nothing was posted to the UI")
            time.sleep(0.01)
        while not self.gui._ui_calls.empty():
            self.gui._ui_calls.get_nowait()()


class FindCameraDialogTests(_GuiTestCase):

    def setUp(self):
        super().setUp()
        self.gui.ip_entry = ttk.Entry(self.root)
        self.gui.ip_entry.pack()
        self.discover_threads = []

    def _configure(self, ip, mac=""):
        self.gui.config_manager.camera.ip_address = ip
        self.gui.config_manager.camera.mac_address = mac

    def _open(self, entry_text, result=CAMERAS):
        self.gui.ip_entry.insert(0, entry_text)

        def fake_discover():
            self.discover_threads.append(threading.current_thread())
            return result

        with mock.patch.object(gui_app, "discover", side_effect=fake_discover):
            self.gui.find_camera()
            self._drain()
        self.root.update()
        return self._dialog()

    def _dialog(self):
        return next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))

    def _tree(self, dialog):
        return next(w for w in _walk(dialog) if isinstance(w, ttk.Treeview))

    def _rows(self, dialog):
        tree = self._tree(dialog)
        return [tree.item(iid, "values") for iid in tree.get_children()]

    def _status(self, dialog):
        # The first label is the search status line.
        return next(w for w in _walk(dialog) if isinstance(w, ttk.Label)).cget("text")

    def _button(self, dialog, text):
        return next(w for w in _walk(dialog)
                    if isinstance(w, ttk.Button) and w.cget("text") == text)

    # -- basics ------------------------------------------------------------

    def test_search_runs_off_the_tk_thread(self):
        self._open(OLD_IP)
        self.assertEqual(len(self.discover_threads), 1)
        self.assertIsNot(self.discover_threads[0], threading.main_thread())

    def test_lists_cameras_and_preselects_the_current_one(self):
        dialog = self._open(f"{OLD_IP}:554")
        rows = self._rows(dialog)
        self.assertEqual(rows[0], (f"{OLD_IP} (current)", "I81EM", MINE, "ONVIF + SADP"))
        self.assertEqual(rows[1], ("192.168.171.30", "IPC-HDW2431T", "-", "ONVIF"))
        tree = self._tree(dialog)
        self.assertEqual(tree.selection(), (tree.get_children()[0],))
        self.assertEqual(str(self._button(dialog, "Use Selected").cget("state")), "normal")

    def test_use_selected_keeps_custom_port_saves_and_closes(self):
        self._configure("192.168.171.99:8554")  # no MAC saved yet
        dialog = self._open("192.168.171.99:8554")
        tree = self._tree(dialog)
        self.assertEqual(tree.selection(), ())  # configured IP not found - nothing preselected
        tree.selection_set(tree.get_children()[1])
        self.root.update()
        self._button(dialog, "Use Selected").invoke()

        self.assertEqual(self.gui.ip_entry.get(), "192.168.171.30:8554")
        camera = self.gui.config_manager.camera
        self.assertEqual(camera.ip_address, "192.168.171.30:8554")
        self.assertEqual(camera.mac_address, "")  # that camera's MAC is unknown - relearned later
        self.gui.config_manager.save_to_file.assert_called_once()
        self.assertFalse(dialog.winfo_exists())
        message = self.gui.log_message.call_args_list[-1].args[1]
        self.assertIn("Camera address set to 192.168.171.30:8554", message)

    def test_not_activated_is_flagged(self):
        cams = [DiscoveredCamera(ip="192.168.1.64", model="DS-2CD2043", activated=False,
                                 sources={"SADP"})]
        self.assertEqual(self._rows(self._open("", result=cams))[0][1],
                         "DS-2CD2043 (not activated)")

    def test_no_cameras_says_so(self):
        dialog = self._open(OLD_IP, result=[])
        self.assertEqual(self._rows(dialog), [])
        self.gui.log_message.assert_called_with("INFO", "Find Camera: no cameras answered")

    def test_entry_locked_during_capture_is_not_changed(self):
        dialog = self._open(OLD_IP)
        self.gui.ip_entry.configure(state=tk.DISABLED)
        with mock.patch.object(gui_app.messagebox, "showwarning") as warn:
            self._button(dialog, "Use Selected").invoke()
        warn.assert_called_once()
        self.assertEqual(self.gui.ip_entry.get(), OLD_IP)
        self.assertTrue(dialog.winfo_exists())
        self.gui.config_manager.save_to_file.assert_not_called()

    def test_result_after_dialog_closed_is_ignored(self):
        release = threading.Event()

        def slow_discover():
            release.wait(5)
            return CAMERAS

        self.gui.ip_entry.insert(0, OLD_IP)
        with mock.patch.object(gui_app, "discover", side_effect=slow_discover):
            self.gui.find_camera()
            self.root.update()
            self._dialog().destroy()
            release.set()
            self._drain()  # must not raise on the destroyed dialog
        self.gui.log_message.assert_not_called()

    # -- recognising the camera by its saved MAC ---------------------------

    def test_moved_camera_is_recognised_by_mac(self):
        # The router moved the camera to .35 and gave its old address to another device.
        self._configure(f"{OLD_IP}:554", MINE)
        cams = [DiscoveredCamera(ip=OLD_IP, mac=OTHER, model="Doorbell", sources={"ONVIF"}),
                DiscoveredCamera(ip=NEW_IP, mac=MINE, model="I81EM", sources={"SADP"})]
        dialog = self._open(f"{OLD_IP}:554", result=cams)

        rows = self._rows(dialog)
        self.assertEqual(rows[0][0], OLD_IP)  # not "(current)" - it's someone else now
        self.assertEqual(rows[1][0], f"{NEW_IP} (your camera)")
        tree = self._tree(dialog)
        self.assertEqual(tree.selection(), (tree.get_children()[1],))
        self.assertIn(f"moved from {OLD_IP} to {NEW_IP}", self._status(dialog))

        self._button(dialog, "Use Selected").invoke()
        camera = self.gui.config_manager.camera
        self.assertEqual(self.gui.ip_entry.get(), f"{NEW_IP}:554")
        self.assertEqual((camera.ip_address, camera.mac_address), (f"{NEW_IP}:554", MINE))
        self.gui.config_manager.save_to_file.assert_called_once()

    def test_saved_camera_missing_and_old_ip_taken(self):
        self._configure(OLD_IP, MINE)
        cams = [DiscoveredCamera(ip=OLD_IP, mac=OTHER, model="Doorbell", sources={"ONVIF"})]
        dialog = self._open(OLD_IP, result=cams)
        self.assertEqual(self._rows(dialog)[0][0], OLD_IP)
        self.assertEqual(self._tree(dialog).selection(), ())
        status = self._status(dialog)
        self.assertIn(f"not yours (MAC {MINE})", status)
        self.assertIn(f"The device at {OLD_IP} is a different camera", status)

    def test_saved_mac_ignored_when_field_holds_another_host(self):
        # The user typed a new address but it isn't saved yet: the saved MAC is
        # about the old camera and must not tag anything.
        self._configure(OLD_IP, MINE)
        cams = [DiscoveredCamera(ip=NEW_IP, mac=MINE, sources={"SADP"})]
        dialog = self._open("192.168.171.50", result=cams)
        self.assertEqual(self._rows(dialog)[0][0], NEW_IP)
        self.assertEqual(self._tree(dialog).selection(), ())


class CameraMacLearningTests(_GuiTestCase):

    def _join_lookups(self):
        for t in threading.enumerate():
            if t.name == "camera-mac":
                t.join(5)

    def test_learns_and_saves_mac_off_the_tk_thread(self):
        self.gui.config_manager.camera.ip_address = f"{OLD_IP}:554"
        threads = []

        def fake_lookup(host):
            threads.append(threading.current_thread())
            return MINE

        with mock.patch.object(gui_app, "lookup_mac", side_effect=fake_lookup) as lookup:
            self.gui._learn_camera_mac(f"{OLD_IP}:554")
            self._drain()
        lookup.assert_called_once_with(OLD_IP)
        self.assertIsNot(threads[0], threading.main_thread())
        self.assertEqual(self.gui.config_manager.camera.mac_address, MINE)
        self.gui.config_manager.save_to_file.assert_called_once()
        self.assertIn(f"Camera MAC {MINE} saved", self.gui.log_message.call_args.args[1])

    def test_once_per_host_unless_forced(self):
        self.gui.config_manager.camera.ip_address = OLD_IP
        with mock.patch.object(gui_app, "lookup_mac", return_value=MINE) as lookup:
            self.gui._learn_camera_mac(OLD_IP)
            self._join_lookups()
            self.gui._learn_camera_mac(OLD_IP)        # capture reconnect - skipped
            self.gui._learn_camera_mac(OLD_IP, force=True)  # Test Connection - runs
            self._join_lookups()
        self.assertEqual(lookup.call_count, 2)

    def test_unchanged_mac_is_not_resaved(self):
        camera = self.gui.config_manager.camera
        camera.ip_address, camera.mac_address = OLD_IP, MINE
        with mock.patch.object(gui_app, "lookup_mac", return_value=MINE):
            self.gui._learn_camera_mac(OLD_IP)
            self._drain()
        self.gui.config_manager.save_to_file.assert_not_called()
        self.gui.log_message.assert_not_called()

    def test_off_network_camera_stores_nothing(self):
        self.gui.config_manager.camera.ip_address = "203.0.113.5:1554"
        with mock.patch.object(gui_app, "lookup_mac", return_value=None):
            self.gui._learn_camera_mac("203.0.113.5:1554")
            self._join_lookups()
        self.assertTrue(self.gui._ui_calls.empty())
        self.assertEqual(self.gui.config_manager.camera.mac_address, "")

    def test_address_changed_during_lookup_is_not_stored(self):
        camera = self.gui.config_manager.camera
        camera.ip_address = OLD_IP
        with mock.patch.object(gui_app, "lookup_mac", return_value=MINE):
            self.gui._learn_camera_mac(OLD_IP)
            self._join_lookups()
        camera.ip_address = NEW_IP  # e.g. the user picked another camera meanwhile
        self._drain()
        self.assertEqual(camera.mac_address, "")
        self.gui.config_manager.save_to_file.assert_not_called()

    def test_typing_a_different_host_drops_the_saved_mac(self):
        camera = self.gui.config_manager.camera
        camera.ip_address, camera.mac_address = OLD_IP, MINE
        self.gui._sync_camera_address(f"{OLD_IP}:554")  # same camera, port added
        self.assertEqual(camera.mac_address, MINE)
        self.gui._sync_camera_address(NEW_IP)  # a different host
        self.assertEqual((camera.ip_address, camera.mac_address), (NEW_IP, ""))


if __name__ == "__main__":
    unittest.main()
