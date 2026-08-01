"""Unit tests for MQTT video delivery (src/gui_app.py, src/config_manager.py).

The delivery path is what a no-internet observatory PC relies on, so these cover
the contract an external consumer sees - metadata first, then the raw video, on
`<base>/metadata` and `<base>/video` - plus every way delivery can fail without
taking the render down with it.

No socket is ever opened: `paho.mqtt.client` is imported *inside* `_send_mqtt`
(so the app runs without paho installed), which means `mock.patch("gui_app.mqtt")`
has nothing to patch. The fake is injected into `sys.modules` instead, as a real
package chain, so `import paho.mqtt.client as mqtt` binds to it.

The app instance is built with `__new__` (no Tk), as in test_gui_discord_tray.py.
"""

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import gui_app  # noqa: E402
from config_manager import AstroScheduleConfig, ConfigManager  # noqa: E402
from gui_app import RTSPTimelapseGUI  # noqa: E402

DATE_STR = "2026-07-25"


def _bare_app():
    """An app instance without __init__/Tk - only safe for self-contained helpers."""
    return gui_app.RTSPTimelapseGUI.__new__(gui_app.RTSPTimelapseGUI)


def _fake_paho(published=True):
    """A stand-in `paho` package whose .mqtt.client is a MagicMock module.

    Returns (modules_dict, client_module) - the dict goes to mock.patch.dict on
    sys.modules, the module is where Client/CallbackAPIVersion are asserted.
    """
    client_module = mock.MagicMock(name="paho.mqtt.client")
    client_module.Client.return_value.publish.return_value.is_published.return_value = published

    paho = types.ModuleType("paho")
    mqtt_pkg = types.ModuleType("paho.mqtt")
    paho.mqtt = mqtt_pkg
    mqtt_pkg.client = client_module

    modules = {"paho": paho, "paho.mqtt": mqtt_pkg, "paho.mqtt.client": client_module}
    return modules, client_module


class SendMqttTests(unittest.TestCase):
    """_send_mqtt: what gets published, and every path that returns False."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.video = Path(self._tmp.name) / "timelapse-2026-07-25.mp4"
        self.video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 1024)

        self.app = _bare_app()
        self.app.log_message = mock.MagicMock()
        self.app.config_manager = mock.MagicMock()
        # A real dataclass, so the code under test reads real values (a MagicMock
        # would make every size/QoS comparison meaningless).
        self.cfg = AstroScheduleConfig(
            delivery_method="mqtt",
            mqtt_broker_host="192.168.1.50",
            mqtt_broker_port=1883,
            mqtt_username="relay",
            mqtt_password="secret",
            mqtt_base_topic="rtsp-timelapse",
            mqtt_qos=1,
        )
        self.app.config_manager.astro_schedule = self.cfg

    def _logged(self, level=None):
        """Every logged message, optionally filtered by level."""
        return [args[1] for args, _ in self.app.log_message.call_args_list
                if level is None or args[0] == level]

    def test_publishes_metadata_then_video(self):
        modules, client_module = _fake_paho()
        with mock.patch.dict(sys.modules, modules):
            ok = self.app._send_mqtt(self.video, DATE_STR)

        self.assertTrue(ok, self._logged())
        client = client_module.Client.return_value
        client.username_pw_set.assert_called_once_with("relay", "secret")
        client.tls_set.assert_not_called()
        client.connect.assert_called_once_with("192.168.1.50", 1883, keepalive=30)

        first, second = client.publish.call_args_list
        self.assertEqual(first.args[0], "rtsp-timelapse/metadata")
        self.assertEqual(second.args[0], "rtsp-timelapse/video")
        for call in (first, second):
            self.assertEqual(call.kwargs, {"qos": 1, "retain": False})

        # The video part is the file's raw bytes; metadata is JSON about it.
        self.assertEqual(second.args[1], self.video.read_bytes())
        import json
        meta = json.loads(first.args[1])
        self.assertEqual(meta["filename"], self.video.name)
        self.assertEqual(meta["date"], DATE_STR)
        self.assertEqual(meta["size_bytes"], self.video.stat().st_size)
        self.assertIn(DATE_STR, meta["message"])

        # The network loop must run, or the QoS-1 PUBACK is never read.
        client.loop_start.assert_called_once()
        client.disconnect.assert_called_once()
        client.loop_stop.assert_called_once()

    def test_base_topic_is_normalised(self):
        self.cfg.mqtt_base_topic = "  /allsky/site1/  "
        modules, client_module = _fake_paho()
        with mock.patch.dict(sys.modules, modules):
            self.assertTrue(self.app._send_mqtt(self.video, DATE_STR))

        topics = [c.args[0] for c in client_module.Client.return_value.publish.call_args_list]
        self.assertEqual(topics, ["allsky/site1/metadata", "allsky/site1/video"])

    def test_tls_and_anonymous_broker(self):
        self.cfg.mqtt_use_tls = True
        self.cfg.mqtt_username = ""
        modules, client_module = _fake_paho()
        with mock.patch.dict(sys.modules, modules):
            self.assertTrue(self.app._send_mqtt(self.video, DATE_STR))

        client = client_module.Client.return_value
        client.tls_set.assert_called_once_with()
        client.username_pw_set.assert_not_called()

    def test_connection_refused_is_reported_not_raised(self):
        modules, client_module = _fake_paho()
        client_module.Client.return_value.connect.side_effect = ConnectionRefusedError(
            "[WinError 10061] No connection could be made")
        with mock.patch.dict(sys.modules, modules):
            ok = self.app._send_mqtt(self.video, DATE_STR)

        self.assertFalse(ok)
        errors = self._logged("ERROR")
        self.assertTrue(any("Delivery failed" in m for m in errors), errors)
        client_module.Client.return_value.publish.assert_not_called()

    def test_unconfirmed_publish_is_a_failure(self):
        """QoS 1 without a PUBACK means the broker never took the video."""
        modules, client_module = _fake_paho(published=False)
        with mock.patch.dict(sys.modules, modules):
            ok = self.app._send_mqtt(self.video, DATE_STR)

        self.assertFalse(ok)
        self.assertTrue(any("did not confirm" in m for m in self._logged("ERROR")))

    def test_missing_file_never_connects(self):
        modules, client_module = _fake_paho()
        with mock.patch.dict(sys.modules, modules):
            ok = self.app._send_mqtt(self.video.with_name("gone.mp4"), DATE_STR)

        self.assertFalse(ok)
        client_module.Client.assert_not_called()
        self.assertTrue(any("not found" in m for m in self._logged("ERROR")))

    def test_no_broker_host_skips_delivery(self):
        self.cfg.mqtt_broker_host = "   "
        modules, client_module = _fake_paho()
        with mock.patch.dict(sys.modules, modules):
            ok = self.app._send_mqtt(self.video, DATE_STR)

        self.assertFalse(ok)
        client_module.Client.assert_not_called()
        self.assertTrue(any("No broker host" in m for m in self._logged("WARNING")))

    def test_oversize_without_auto_reduce_is_skipped(self):
        self.cfg.discord_max_video_size_mb = 1
        self.cfg.discord_auto_quality_reduction = False
        self.video.write_bytes(b"\x00" * (2 * 1024 * 1024))

        modules, client_module = _fake_paho()
        with mock.patch.dict(sys.modules, modules):
            ok = self.app._send_mqtt(self.video, DATE_STR)

        self.assertFalse(ok)
        client_module.Client.return_value.publish.assert_not_called()
        self.assertTrue(any("exceeds limit" in m for m in self._logged("WARNING")))

    def test_oversize_with_auto_reduce_publishes_the_reencode(self):
        """The shared re-encode ladder feeds the MQTT publish, same as Discord."""
        self.cfg.discord_max_video_size_mb = 1
        self.cfg.discord_auto_quality_reduction = True
        self.video.write_bytes(b"\x00" * (2 * 1024 * 1024))

        smaller = Path(self._tmp.name) / ".discord_encode" / "discord_crf25.mp4"
        smaller.parent.mkdir()
        smaller.write_bytes(b"\x00" * 1024)
        self.app._reencode_for_discord = mock.MagicMock(return_value=smaller)

        modules, client_module = _fake_paho()
        with mock.patch.dict(sys.modules, modules):
            ok = self.app._send_mqtt(self.video, DATE_STR)

        self.assertTrue(ok, self._logged())
        self.app._reencode_for_discord.assert_called_once_with(self.video, 1)
        calls = client_module.Client.return_value.publish.call_args_list
        self.assertEqual(len(calls[1].args[1]), 1024)  # the re-encoded bytes
        # ...but named after the render, not the scratch encode: a consumer saving
        # "discord_crf25.mp4" would overwrite the same file every night.
        import json
        self.assertEqual(json.loads(calls[0].args[1])["filename"], self.video.name)
        # The scratch dir is cleaned up exactly as on the Discord path.
        self.assertFalse(smaller.exists())
        self.assertFalse(smaller.parent.exists())

    def test_reencoded_webm_render_is_named_by_what_is_sent(self):
        """The ladder always writes .mp4, so a re-encoded .webm must not stay .webm."""
        webm = Path(self._tmp.name) / "timelapse-2026-07-25.webm"
        webm.write_bytes(b"\x00" * (2 * 1024 * 1024))
        self.cfg.discord_max_video_size_mb = 1
        self.cfg.discord_auto_quality_reduction = True

        smaller = Path(self._tmp.name) / ".discord_encode" / "discord_crf25.mp4"
        smaller.parent.mkdir()
        smaller.write_bytes(b"\x00" * 1024)
        self.app._reencode_for_discord = mock.MagicMock(return_value=smaller)

        modules, client_module = _fake_paho()
        with mock.patch.dict(sys.modules, modules):
            self.assertTrue(self.app._send_mqtt(webm, DATE_STR), self._logged())

        import json
        meta = json.loads(client_module.Client.return_value.publish.call_args_list[0].args[1])
        self.assertEqual(meta["filename"], "timelapse-2026-07-25.mp4")

    def test_missing_paho_is_reported_not_raised(self):
        # A None entry in sys.modules is how the import system spells "absent".
        with mock.patch.dict(sys.modules, {"paho": None, "paho.mqtt": None,
                                           "paho.mqtt.client": None}):
            ok = self.app._send_mqtt(self.video, DATE_STR)

        self.assertFalse(ok)
        self.assertTrue(any("paho-mqtt is not installed" in m for m in self._logged("ERROR")))


class DeliverVideoDispatchTests(unittest.TestCase):
    """_deliver_video routes to exactly one method - MagicMock stands in for self."""

    def _gui(self, method):
        g = mock.MagicMock()
        g.config_manager.astro_schedule.delivery_method = method
        return g

    def test_discord_method_uses_the_webhook(self):
        g = self._gui("discord")
        RTSPTimelapseGUI._deliver_video(g, Path("v.mp4"), DATE_STR)
        g._send_discord_webhook.assert_called_once_with(Path("v.mp4"), DATE_STR)
        g._send_mqtt.assert_not_called()

    def test_mqtt_method_uses_the_broker(self):
        g = self._gui("mqtt")
        RTSPTimelapseGUI._deliver_video(g, Path("v.mp4"), DATE_STR)
        g._send_mqtt.assert_called_once_with(Path("v.mp4"), DATE_STR)
        g._send_discord_webhook.assert_not_called()

    def test_unknown_method_falls_back_to_discord(self):
        """A hand-edited config must not silently deliver nowhere."""
        g = self._gui("carrier-pigeon")
        RTSPTimelapseGUI._deliver_video(g, Path("v.mp4"), DATE_STR)
        g._send_discord_webhook.assert_called_once()

    def test_result_is_passed_through(self):
        g = self._gui("mqtt")
        g._send_mqtt.return_value = False
        self.assertFalse(RTSPTimelapseGUI._deliver_video(g, Path("v.mp4"), DATE_STR))


class ClosingFlushesIntegrationsTests(unittest.TestCase):
    """Closing the window must not drop a half-typed Integrations field.

    Those widgets save on <FocusOut>/<Return>; closing the window with an entry
    still focused fires neither, so the broker host (or webhook URL) typed as the
    very last action would never reach the config.
    """

    def _gui(self):
        g = mock.MagicMock()
        g.is_capturing = False
        return g

    def test_integrations_panel_is_saved_before_the_config_write(self):
        g = self._gui()
        order = []
        g.integrations_panel._save_to_config.side_effect = lambda: order.append("panel")
        g.save_config.side_effect = lambda: order.append("config")

        RTSPTimelapseGUI.on_closing(g)

        self.assertEqual(order, ["panel", "config"], "the panel must flush first")
        g.root.destroy.assert_called_once()

    def test_a_failing_panel_save_still_closes_the_window(self):
        g = self._gui()
        g.integrations_panel._save_to_config.side_effect = RuntimeError("tk is gone")

        RTSPTimelapseGUI.on_closing(g)

        g.save_config.assert_called_once()
        g.root.destroy.assert_called_once()
        level, _ = g.log_message.call_args[0]
        self.assertEqual(level, "WARNING")


class MqttConfigValidationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = ConfigManager()

    def test_defaults_are_valid(self):
        valid, errors = self.cfg.validate()
        self.assertTrue(valid, errors)

    def test_defaults_are_the_discord_method(self):
        self.assertEqual(self.cfg.astro_schedule.delivery_method, "discord")

    def test_unknown_delivery_method_rejected(self):
        self.cfg.astro_schedule.delivery_method = "smoke-signal"
        valid, errors = self.cfg.validate()
        self.assertFalse(valid)
        self.assertTrue(any("Delivery method" in e for e in errors), errors)

    def test_qos_2_rejected(self):
        self.cfg.astro_schedule.mqtt_qos = 2
        valid, errors = self.cfg.validate()
        self.assertFalse(valid)
        self.assertTrue(any("QoS" in e for e in errors), errors)

    def test_port_out_of_range_rejected(self):
        self.cfg.astro_schedule.mqtt_broker_port = 70000
        valid, errors = self.cfg.validate()
        self.assertFalse(valid)
        self.assertTrue(any("MQTT port" in e for e in errors), errors)

    def test_wildcard_topic_rejected_only_when_mqtt_is_selected(self):
        self.cfg.astro_schedule.mqtt_base_topic = "rtsp/#"
        valid, _ = self.cfg.validate()
        self.assertTrue(valid, "a stale topic must not fail a Discord config")

        self.cfg.astro_schedule.delivery_method = "mqtt"
        valid, errors = self.cfg.validate()
        self.assertFalse(valid)
        self.assertTrue(any("base topic" in e for e in errors), errors)

    def test_empty_topic_rejected_when_mqtt_is_selected(self):
        self.cfg.astro_schedule.delivery_method = "mqtt"
        self.cfg.astro_schedule.mqtt_base_topic = ""
        valid, errors = self.cfg.validate()
        self.assertFalse(valid)
        self.assertTrue(any("base topic" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
