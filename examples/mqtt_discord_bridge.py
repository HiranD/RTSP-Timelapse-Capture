#!/usr/bin/env python3
"""MQTT -> Discord bridge for RTSP Timelapse Capture.

Run this on a machine **with** internet. It subscribes to the broker the capture
PC publishes to and forwards each finished timelapse (and any plain-text message)
to a Discord webhook you own. Nothing in here is specific to one setup: point it
at your broker, your topic and your webhook.

Why it exists: the capture PC may be offline (an observatory rig with only a
local Mosquitto broker). It publishes the video to the broker; this script - on
the other side of the fence - does the uploading.

Topic contract (what the app publishes, and what this script expects):

    <base>/metadata   JSON {"message", "filename", "date", "size_bytes"}
                      Published first. Never retained.
    <base>/video      Raw MP4 (or WebM) bytes. Published second.
                      Consumers must tolerate metadata being absent.

Any other `<base>/...` subtopic carrying UTF-8 text is posted to Discord as a
plain message, so the same bridge can relay status notes from other tools.

Usage:

    python mqtt_discord_bridge.py --broker 192.168.1.50 \
        --username relay --password secret \
        --webhook https://discord.com/api/webhooks/...

Every option also reads an environment variable, so nothing sensitive has to go
on the command line:

    MQTT_BROKER  MQTT_PORT  MQTT_USERNAME  MQTT_PASSWORD  MQTT_BASE_TOPIC
    MQTT_TLS (1/true/yes)   DISCORD_WEBHOOK_URL

Requires: paho-mqtt  (pip install paho-mqtt). The upload uses only the standard
library.

Size limits: a Discord webhook accepts roughly 10 MB per attachment, and a
broker enforces its own maximum message size (Mosquitto's `message_size_limit`,
unlimited by default). Keep the app's "Max upload size (MB)" under both - the
app skips delivery instead of sending something that can't get through.

Runs until interrupted (Ctrl+C); it reconnects on its own if the broker restarts.
"""

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
import uuid

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("paho-mqtt is required: pip install paho-mqtt")


log = logging.getLogger("mqtt-discord-bridge")

# Container sniffing by magic bytes - the payload is raw bytes with no filename
# of its own if metadata never arrived.
MP4_BRAND_OFFSET = slice(4, 8)
MP4_BRAND = b"ftyp"
WEBM_MAGIC = b"\x1a\x45\xdf\xa3"

MIME_TYPES = {"mp4": "video/mp4", "webm": "video/webm"}


def env_flag(name: str) -> bool:
    """Read a boolean environment variable ('1', 'true', 'yes' are all true)."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Forward timelapse videos published over MQTT to a Discord webhook.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--broker", default=os.environ.get("MQTT_BROKER"),
                        help="MQTT broker hostname or IP [env: MQTT_BROKER]")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", 1883)),
                        help="MQTT broker port [env: MQTT_PORT]")
    parser.add_argument("--username", default=os.environ.get("MQTT_USERNAME", ""),
                        help="Broker username (omit for an anonymous broker) [env: MQTT_USERNAME]")
    parser.add_argument("--password", default=os.environ.get("MQTT_PASSWORD", ""),
                        help="Broker password [env: MQTT_PASSWORD]")
    parser.add_argument("--base-topic", default=os.environ.get("MQTT_BASE_TOPIC", "rtsp-timelapse"),
                        help="Base topic the app publishes to [env: MQTT_BASE_TOPIC]")
    parser.add_argument("--tls", action="store_true", default=env_flag("MQTT_TLS"),
                        help="Connect to the broker over TLS [env: MQTT_TLS]")
    parser.add_argument("--webhook", default=os.environ.get("DISCORD_WEBHOOK_URL"),
                        help="Discord webhook URL to post to [env: DISCORD_WEBHOOK_URL]")
    parser.add_argument("--verbose", action="store_true", help="Log every message received")

    args = parser.parse_args(argv)
    if not args.broker:
        parser.error("a broker is required (--broker or MQTT_BROKER)")
    if not args.webhook:
        parser.error("a Discord webhook is required (--webhook or DISCORD_WEBHOOK_URL)")
    args.base_topic = args.base_topic.strip().strip("/")
    if not args.base_topic:
        parser.error("--base-topic must not be empty")
    return args


# ----------------------------------------------------------------- Discord

def encode_multipart(fields):
    """Build a multipart/form-data body.

    fields: list of (name, value) where value is either bytes/str (a plain field)
    or a (filename, bytes, content_type) tuple (a file part).
    """
    boundary = uuid.uuid4().hex
    body = bytearray()

    for name, value in fields:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        if isinstance(value, tuple):
            filename, content, content_type = value
            body.extend(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                .encode("utf-8")
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
            body.extend(content)
        else:
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            body.extend(value if isinstance(value, (bytes, bytearray)) else str(value).encode("utf-8"))
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def post_to_discord(webhook: str, content: str, attachment=None) -> bool:
    """Post a message to the webhook, optionally with a (filename, bytes, mime) file."""
    fields = [("payload_json", ("payload.json",
                                json.dumps({"content": content}).encode("utf-8"),
                                "application/json"))]
    if attachment is not None:
        fields.append(("file", attachment))

    body, content_type = encode_multipart(fields)
    request = urllib.request.Request(webhook, data=body, method="POST")
    request.add_header("Content-Type", content_type)
    request.add_header("User-Agent", "mqtt-discord-bridge")

    try:
        # Generous timeout: a ~10 MB attachment on a slow uplink is still a
        # normal case, and Discord accepts the whole body before responding.
        with urllib.request.urlopen(request, timeout=120):
            return True
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        log.error("Discord rejected the post: HTTP %s %s %s", e.code, e.reason, detail)
    except urllib.error.URLError as e:
        log.error("Could not reach Discord: %s", e.reason)
    except Exception as e:  # noqa: BLE001 - a bridge must not die on one bad post
        log.error("Discord post failed: %s", e)
    return False


# -------------------------------------------------------------------- MQTT

class Bridge:
    """Subscribes to one base topic and relays what arrives to a webhook."""

    def __init__(self, base_topic: str, webhook: str, verbose: bool = False):
        self.base_topic = base_topic
        self.webhook = webhook
        self.verbose = verbose
        # Last metadata seen, keyed by the parent topic of <...>/metadata, so a
        # nested base (site1/rtsp-timelapse) can't be confused with another.
        self._metadata = {}

    # -- paho callbacks (CallbackAPIVersion.VERSION2 signatures) --

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            log.error("Broker refused the connection: %s", reason_code)
            return
        topic = f"{self.base_topic}/#"
        client.subscribe(topic, qos=1)
        log.info("Connected; subscribed to %s", topic)

    def on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            log.warning("Disconnected from the broker (%s); retrying...", reason_code)

    def on_message(self, client, userdata, msg):
        # Retained messages replay on every reconnect - relaying them would post
        # the same video again each time the broker or this script restarts.
        if msg.retain:
            log.debug("Ignoring retained message on %s", msg.topic)
            return

        if self.verbose:
            log.info("Message on %s (%d bytes)", msg.topic, len(msg.payload))

        parent, _, leaf = msg.topic.rpartition("/")
        try:
            if leaf == "metadata":
                self._on_metadata(parent, msg.payload)
            elif leaf == "video":
                self._on_video(parent, msg.payload)
            else:
                self._on_text(msg.topic, msg.payload)
        except Exception as e:  # noqa: BLE001 - keep the loop alive
            log.error("Failed to handle %s: %s", msg.topic, e)

    # -- handlers --

    def _on_metadata(self, parent: str, payload: bytes):
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            log.warning("Ignoring unparseable metadata on %s/metadata: %s", parent, e)
            return
        if not isinstance(data, dict):
            log.warning("Ignoring metadata on %s/metadata: expected a JSON object", parent)
            return
        self._metadata[parent] = data
        log.info("Metadata: %s", data.get("filename") or data.get("date") or data)

    def _on_video(self, parent: str, payload: bytes):
        extension = self._detect_container(payload)
        if extension is None:
            log.warning("Ignoring %s/video: not an MP4 or WebM (%d bytes)", parent, len(payload))
            return

        # Metadata is best-effort: the video is forwarded either way.
        meta = self._metadata.pop(parent, {})
        date = str(meta.get("date") or "unknown-date")
        filename = str(meta.get("filename") or f"timelapse-{date}.{extension}")
        caption = str(meta.get("message") or f"Timelapse video completed for {date}")

        size_mb = len(payload) / (1024 * 1024)
        log.info("Forwarding %s (%.1f MB) to Discord...", filename, size_mb)
        if post_to_discord(self.webhook, caption,
                           (filename, payload, MIME_TYPES[extension])):
            log.info("Uploaded %s to Discord", filename)

    def _on_text(self, topic: str, payload: bytes):
        try:
            text = payload.decode("utf-8").strip()
        except UnicodeDecodeError:
            log.debug("Ignoring non-text payload on %s", topic)
            return
        if not text:
            return
        if post_to_discord(self.webhook, text):
            log.info("Relayed message from %s", topic)

    @staticmethod
    def _detect_container(payload: bytes):
        """Return 'mp4' / 'webm' from the payload's magic bytes, else None."""
        if len(payload) >= 8 and payload[MP4_BRAND_OFFSET] == MP4_BRAND:
            return "mp4"
        if payload[:4] == WEBM_MAGIC:
            return "webm"
        return None


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    bridge = Bridge(args.base_topic, args.webhook, verbose=args.verbose)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = bridge.on_connect
    client.on_disconnect = bridge.on_disconnect
    client.on_message = bridge.on_message
    if args.username:
        client.username_pw_set(args.username, args.password)
    if args.tls:
        client.tls_set()

    # Keep running across broker restarts: connect_async + loop_forever retries
    # the first connection too, so the bridge can start before the broker does.
    client.reconnect_delay_set(min_delay=5, max_delay=120)
    client.connect_async(args.broker, args.port, keepalive=60)

    log.info("Bridging %s/# from %s:%s to Discord", args.base_topic, args.broker, args.port)
    try:
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        log.info("Stopping...")
        client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
