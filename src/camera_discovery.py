"""
Camera discovery - find IP cameras on the local network (the Find Camera button).

Sends two read-only multicast probes and collects the replies:
    * ONVIF WS-Discovery (UDP 3702) - answered by most IP camera brands.
    * Hikvision SADP "inquiry" (UDP 37020) - answered by Hikvision and its OEMs
      (Annke, ...); it's the camera's "Enable Multicast Discovery" setting.

Both go to 239.255.255.250 with TTL 1, so only the local subnet sees them, and
cameras reply unicast to the probe socket's own port - nothing listens on a
fixed port or joins a multicast group. Verified against an Annke I81EM: both
replies arrive within milliseconds.

SADP can also activate a camera, reset its password and change its IP. Only
the inquiry is implemented here, on purpose - discovery must never change a
camera. SADP replies also carry password-reset material (Salt, ...), so never
log or display a raw reply: only the parsed DiscoveredCamera fields.

lookup_mac() reads a device's MAC from Windows' ARP table. The GUI saves the
camera's MAC after each successful connection, so Find can recognise the
camera after DHCP moves it to a new address.

Tk-agnostic and standard-library only. The GUI runs discover() and lookup_mac()
on background threads and hands the results back to the Tk thread itself.
"""

import ctypes
import re
import select
import socket
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from typing import Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import unquote

from app_logging import get_logger

LOG = get_logger("discovery")

MULTICAST_GROUP = "239.255.255.250"
SADP_PORT = 37020
ONVIF_PORT = 3702

# (protocol, host, port) - injectable so tests can aim the loop at a fake camera.
DEFAULT_TARGETS: Tuple[Tuple[str, str, int], ...] = (
    ("SADP", MULTICAST_GROUP, SADP_PORT),
    ("ONVIF", MULTICAST_GROUP, ONVIF_PORT),
)

DEFAULT_TIMEOUT_S = 3.0

# The probe pair goes out this many times, this far apart: UDP can drop a
# datagram and WS-Discovery itself repeats its multicast messages. Duplicate
# replies are merged.
_PROBE_REPEATS = 2
_PROBE_GAP_S = 0.25
_RECV_BUFSIZE = 65535

_ONVIF_SCOPE_PREFIX = "onvif://www.onvif.org/"
_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}([-:]?[0-9A-Fa-f]{2}){5}$")


class DiscoveryError(Exception):
    """The search couldn't run at all (no interface could send a probe)."""


@dataclass
class DiscoveredCamera:
    """One device that answered a probe. Only ip is guaranteed."""

    ip: str                          # address the reply came from - reachable by definition
    mac: Optional[str] = None        # normalised "24:48:45:00:00:01"
    model: Optional[str] = None      # SADP DeviceDescription / ONVIF hardware scope
    serial: Optional[str] = None     # SADP DeviceSN
    dhcp: Optional[bool] = None      # SADP only
    activated: Optional[bool] = None  # SADP only; False = a brand-new Hikvision camera
    sources: Set[str] = field(default_factory=set)  # {"SADP", "ONVIF"}

    @property
    def sources_label(self) -> str:
        """e.g. "ONVIF + SADP" - stable order for display."""
        return " + ".join(sorted(self.sources))


# ----------------------------------------------------------------- probes

def build_sadp_probe() -> bytes:
    """The SADP inquiry - the only SADP message this module ever sends."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f"<Probe><Uuid>{str(uuid.uuid4()).upper()}</Uuid><Types>inquiry</Types></Probe>"
    ).encode("utf-8")


def build_onvif_probe() -> bytes:
    """A WS-Discovery Probe for ONVIF video devices (NetworkVideoTransmitter)."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
        'xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
        'xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
        "<e:Header>"
        f"<w:MessageID>uuid:{uuid.uuid4()}</w:MessageID>"
        "<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>"
        "<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>"
        "</e:Header>"
        "<e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body>"
        "</e:Envelope>"
    ).encode("utf-8")


# ---------------------------------------------------------------- parsing

def normalise_mac(value: Optional[str]) -> Optional[str]:
    """ "24-48-45-00-00-01" / "24:48:45:00:00:01" / "244845000001" -> "24:48:45:00:00:01"."""
    text = (value or "").strip()
    if not _MAC_RE.match(text):
        return None
    digits = re.sub(r"[-:]", "", text).lower()
    return ":".join(digits[i:i + 2] for i in range(0, 12, 2))


def _local_name(tag: str) -> str:
    """Tag without its namespace - vendors vary the prefixes."""
    return tag.rsplit("}", 1)[-1]


def _parse_xml(data: bytes) -> Optional[ET.Element]:
    # ElementTree never fetches external entities, and the expat bundled with
    # Python 3.13 rejects entity-expansion bombs; recv caps size at 64 KB.
    try:
        return ET.fromstring(data)
    except (ET.ParseError, ValueError):
        return None


def _parse_bool(text: Optional[str]) -> Optional[bool]:
    value = (text or "").strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def parse_sadp_reply(data: bytes, src_ip: str) -> Optional[DiscoveredCamera]:
    """A SADP <ProbeMatch> reply -> DiscoveredCamera, anything else -> None.

    Reads only the identifying fields. Salt, PasswordResetAbility and the rest
    are deliberately ignored.
    """
    root = _parse_xml(data)
    if root is None or _local_name(root.tag) != "ProbeMatch":
        return None
    fields = {_local_name(child.tag): (child.text or "").strip() for child in root}
    if not (fields.get("MAC") or fields.get("DeviceSN") or fields.get("IPv4Address")):
        return None
    return DiscoveredCamera(
        ip=src_ip,
        mac=normalise_mac(fields.get("MAC")),
        model=fields.get("DeviceDescription") or None,
        serial=fields.get("DeviceSN") or None,
        dhcp=_parse_bool(fields.get("DHCP")),
        activated=_parse_bool(fields.get("Activated")),
        sources={"SADP"},
    )


def parse_onvif_reply(data: bytes, src_ip: str) -> Optional[DiscoveredCamera]:
    """A WS-Discovery ProbeMatches reply from an ONVIF device -> DiscoveredCamera.

    Probes (including our own, if echoed) and non-ONVIF WS-Discovery devices
    such as printers -> None.
    """
    root = _parse_xml(data)
    if root is None or _local_name(root.tag) != "Envelope":
        return None
    match = next((el for el in root.iter() if _local_name(el.tag) == "ProbeMatch"), None)
    if match is None:
        return None

    types = ""
    scopes: List[str] = []
    for el in match.iter():
        name = _local_name(el.tag)
        if name == "Types":
            types = el.text or ""
        elif name == "Scopes":
            scopes = (el.text or "").split()

    onvif_scopes = [s for s in scopes if s.lower().startswith(_ONVIF_SCOPE_PREFIX)]
    if "NetworkVideoTransmitter" not in types and not onvif_scopes:
        return None

    mac = hardware = name_scope = None
    for scope in onvif_scopes:
        key, _, value = scope[len(_ONVIF_SCOPE_PREFIX):].partition("/")
        value = unquote(value).strip()
        key = key.lower()
        if key == "mac" and mac is None:
            mac = normalise_mac(value)
        elif key == "hardware" and not hardware:
            hardware = value
        elif key == "name" and not name_scope:
            name_scope = value

    return DiscoveredCamera(
        ip=src_ip,
        mac=mac,
        model=hardware or name_scope or None,
        sources={"ONVIF"},
    )


def parse_reply(data: bytes, src_ip: str) -> Optional[DiscoveredCamera]:
    """Try both protocols. Replies are matched by content, not source port."""
    return parse_sadp_reply(data, src_ip) or parse_onvif_reply(data, src_ip)


def _ip_sort_key(ip: str):
    try:
        return (0, tuple(int(part) for part in ip.split(".")))
    except ValueError:
        return (1, ip)


def merge(cameras: Iterable[DiscoveredCamera]) -> List[DiscoveredCamera]:
    """One entry per IP: a camera answering SADP and ONVIF becomes one row.

    Each field keeps the first non-None value seen. Sorted by IP.
    """
    by_ip = {}
    for cam in cameras:
        current = by_ip.get(cam.ip)
        if current is None:
            by_ip[cam.ip] = replace(cam, sources=set(cam.sources))
            continue
        for name in ("mac", "model", "serial", "dhcp", "activated"):
            if getattr(current, name) is None:
                setattr(current, name, getattr(cam, name))
        current.sources |= cam.sources
    return sorted(by_ip.values(), key=lambda c: _ip_sort_key(c.ip))


# ---------------------------------------------------------------- network

def _default_route_ip() -> Optional[str]:
    """The IPv4 the OS would use to reach the internet. connect() on UDP sends nothing."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def local_ipv4_addresses() -> List[str]:
    """Every local IPv4 to probe from, minus loopback and link-local (169.254.x).

    Each adapter is probed separately: with VPNs installed (Tailscale,
    ZeroTier, ...) the OS default could otherwise send the probe to the wrong one.
    """
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        infos = []
    ips: List[str] = []
    for info in infos:
        ip = info[4][0]
        if ip.startswith("127.") or ip.startswith("169.254.") or ip in ips:
            continue
        ips.append(ip)
    if not ips:
        fallback = _default_route_ip()
        if fallback and not fallback.startswith("127."):
            ips.append(fallback)
    return ips


def _open_socket(local_ip: str) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
        sock.bind((local_ip, 0))
        sock.setblocking(False)
    except OSError:
        sock.close()
        raise
    return sock


def _send_probes(sock: socket.socket, targets, probes) -> bool:
    """Send every probe from one socket. True if at least one went out."""
    sent = False
    for protocol, host, port in targets:
        try:
            sock.sendto(probes[protocol], (host, port))
            sent = True
        except OSError as e:
            LOG.debug("discovery: %s probe from %s failed: %s",
                      protocol, sock.getsockname()[0], e)
    return sent


def discover(timeout: float = DEFAULT_TIMEOUT_S,
             interfaces: Optional[Sequence[str]] = None,
             targets: Sequence[Tuple[str, str, int]] = DEFAULT_TARGETS) -> List[DiscoveredCamera]:
    """Probe the local network and return the cameras that answered, merged by IP.

    Blocks for `timeout` seconds - call it from a background thread. Raises
    DiscoveryError only if no interface could send a probe at all; a quiet
    network just returns [].
    """
    if interfaces is None:
        interfaces = local_ipv4_addresses()
    probes = {"SADP": build_sadp_probe(), "ONVIF": build_onvif_probe()}

    sockets = []
    for ip in interfaces:
        try:
            sockets.append(_open_socket(ip))
        except OSError as e:
            LOG.debug("discovery: skipping interface %s: %s", ip, e)
    if not sockets:
        raise DiscoveryError("No network connection to search from.")

    found: List[DiscoveredCamera] = []
    try:
        if not any([_send_probes(sock, targets, probes) for sock in sockets]):
            raise DiscoveryError("Could not send the search on any network connection.")
        repeats_left = _PROBE_REPEATS - 1
        next_send = time.monotonic() + _PROBE_GAP_S
        deadline = time.monotonic() + timeout

        while True:
            now = time.monotonic()
            if repeats_left and now >= next_send:
                for sock in sockets:
                    _send_probes(sock, targets, probes)
                repeats_left -= 1
                next_send = now + _PROBE_GAP_S
            if now >= deadline:
                break
            wait = deadline - now
            if repeats_left:
                wait = min(wait, max(0.0, next_send - now))
            readable, _, _ = select.select(sockets, [], [], wait)
            for sock in readable:
                try:
                    data, (src_ip, _src_port) = sock.recvfrom(_RECV_BUFSIZE)
                except OSError:
                    # Windows reports an ICMP "port unreachable" from an earlier
                    # sendto as WSAECONNRESET on the next recv - not a reply.
                    continue
                camera = parse_reply(data, src_ip)
                if camera is not None:
                    found.append(camera)
    finally:
        for sock in sockets:
            sock.close()

    cameras = merge(found)
    for cam in cameras:
        # ONVIF-only cameras of most brands don't put their MAC in the reply. They
        # just answered, so Windows has them in its ARP cache - a lookup is instant.
        if cam.mac is None:
            cam.mac = lookup_mac(cam.ip)
        LOG.debug("discovery: %s model=%s mac=%s via %s",
                  cam.ip, cam.model, cam.mac, cam.sources_label)
    return cameras


def _send_arp(ip: str) -> Optional[bytes]:
    """Raw iphlpapi.SendARP: the hardware address for ip, or None."""
    send_arp = ctypes.windll.iphlpapi.SendARP
    send_arp.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                         ctypes.POINTER(ctypes.c_ulong)]
    send_arp.restype = ctypes.c_ulong
    buf = (ctypes.c_ubyte * 8)()
    size = ctypes.c_ulong(ctypes.sizeof(buf))
    # IPAddr is the address's network-order bytes read as a native DWORD.
    dest = int.from_bytes(socket.inet_aton(ip), sys.byteorder)
    if send_arp(dest, 0, buf, ctypes.byref(size)) != 0:
        return None
    return bytes(buf[:size.value])


def lookup_mac(host: str) -> Optional[str]:
    """The MAC of a device on the local network, e.g. the camera just connected to.

    host may be "ip", "ip:port" or a hostname. Returns None for anything not on the
    local network: Windows' SendARP answers ERROR_BAD_NET_NAME there, after ~3 s,
    and never substitutes the router's MAC (checked 2026-10-24 with a public IP, an
    unused LAN address and another private range). Blocks - call it from a background
    thread. Windows only; None elsewhere.
    """
    host = entry_host(host)
    if sys.platform != "win32" or not host:
        return None
    try:
        ip = socket.gethostbyname(host)
    except (OSError, UnicodeError):
        return None
    if ip.startswith("127."):
        return None
    try:
        raw = _send_arp(ip)
    except (OSError, AttributeError, ValueError):
        return None
    if not raw or len(raw) != 6 or not any(raw):
        return None  # e.g. this PC's own address answers with zero bytes
    return normalise_mac(raw.hex())


# ----------------------------------------------------------------- GUI helpers

def match_configured(cameras: Sequence[DiscoveredCamera], configured_host: str,
                     saved_mac: Optional[str]) -> Tuple[Optional[DiscoveredCamera], bool]:
    """Which found camera is the one the app is set up for -> (camera, moved).

    The saved MAC wins: it survives a DHCP address change, the IP doesn't, and
    after a change the old IP may even belong to a different device. A camera at
    the configured IP whose MAC is unknown can't be ruled out, so it still counts.
    With no saved MAC, the IP decides. moved is True when the MAC match sits at
    a different IP than configured.
    """
    saved_mac = normalise_mac(saved_mac)
    at_configured = next((c for c in cameras if c.ip == configured_host), None)
    if saved_mac:
        mine = next((c for c in cameras if c.mac == saved_mac), None)
        if mine is not None:
            return mine, mine.ip != configured_host
        if at_configured is not None and at_configured.mac is None:
            return at_configured, False
        return None, False
    return at_configured, False


def _split_port(text: str) -> Tuple[str, Optional[str]]:
    """ "192.168.0.101:8554" -> ("192.168.0.101", "8554"); no port -> (text, None)."""
    host, sep, port = text.rpartition(":")
    if sep and host and ":" not in host and port.isdigit():
        return host, port
    return text, None


def entry_host(entry_text: str) -> str:
    """The host part of the IP Address field, without a custom port."""
    return _split_port((entry_text or "").strip())[0]


def replace_host(entry_text: str, new_host: str) -> str:
    """The IP Address field's new value, keeping a custom port the user typed.

    "192.168.0.101:8554" + "10.0.0.5" -> "10.0.0.5:8554"; "192.168.0.101" -> "10.0.0.5".
    """
    _host, port = _split_port((entry_text or "").strip())
    return f"{new_host}:{port}" if port else new_host
