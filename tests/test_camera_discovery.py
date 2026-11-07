"""
Unit tests for camera_discovery (the Capture tab's Find Camera button).

The fixtures in tests/fixtures/discovery/ are real replies from an Annke I81EM
(Hikvision OEM) captured on 2026-10-23, scrubbed: fake serial and MAC, zeroed
SADP Salt, otherwise byte-for-byte what the camera sent.
"""

import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import camera_discovery as cd  # noqa: E402
from camera_discovery import DiscoveredCamera  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "discovery"
SADP_REPLY = (FIXTURES / "sadp_probe_match.xml").read_bytes()
ONVIF_REPLY = (FIXTURES / "onvif_probe_matches.xml").read_bytes()

CAM_IP = "192.168.171.22"
FAKE_MAC = "24:48:45:00:00:01"

PRINTER_REPLY = (
    b'<?xml version="1.0" encoding="utf-8"?>'
    b'<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
    b'xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">'
    b"<soap:Body><wsd:ProbeMatches><wsd:ProbeMatch>"
    b"<wsd:Types>wsdp:Device wprt:PrintDeviceType</wsd:Types>"
    b"<wsd:XAddrs>http://192.168.171.40:80/wsd</wsd:XAddrs>"
    b"</wsd:ProbeMatch></wsd:ProbeMatches></soap:Body></soap:Envelope>"
)

ONVIF_NO_MAC_REPLY = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
    b'xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">'
    b"<s:Body><d:ProbeMatches><d:ProbeMatch>"
    b"<d:Types>dn:NetworkVideoTransmitter</d:Types>"
    b"<d:Scopes>onvif://www.onvif.org/name/Dahua%20IPC "
    b"onvif://www.onvif.org/hardware/IPC-HDW2431T</d:Scopes>"
    b"<d:XAddrs>http://192.168.1.108/onvif/device_service</d:XAddrs>"
    b"</d:ProbeMatch></d:ProbeMatches></s:Body></s:Envelope>"
)


class TestParseSadp(unittest.TestCase):

    def test_real_reply(self):
        cam = cd.parse_sadp_reply(SADP_REPLY, CAM_IP)
        self.assertIsNotNone(cam)
        self.assertEqual(cam.ip, CAM_IP)
        self.assertEqual(cam.mac, FAKE_MAC)  # "24-48-45-00-00-01" normalised
        self.assertEqual(cam.model, "I81EM")
        self.assertEqual(cam.serial, "TEST0000000000000000000000")
        self.assertIs(cam.dhcp, True)
        self.assertIs(cam.activated, True)
        self.assertEqual(cam.sources, {"SADP"})

    def test_ip_is_the_reply_source(self):
        # The source address is what answered us; IPv4Address is only informative.
        cam = cd.parse_sadp_reply(SADP_REPLY, "10.0.0.9")
        self.assertEqual(cam.ip, "10.0.0.9")

    def test_not_activated(self):
        cam = cd.parse_sadp_reply(
            SADP_REPLY.replace(b"<Activated>true", b"<Activated>false"), CAM_IP)
        self.assertIs(cam.activated, False)

    def test_onvif_reply_is_not_sadp(self):
        self.assertIsNone(cd.parse_sadp_reply(ONVIF_REPLY, CAM_IP))

    def test_own_probe_echo_is_not_a_camera(self):
        self.assertIsNone(cd.parse_sadp_reply(cd.build_sadp_probe(), CAM_IP))


class TestParseOnvif(unittest.TestCase):

    def test_real_reply(self):
        cam = cd.parse_onvif_reply(ONVIF_REPLY, CAM_IP)
        self.assertIsNotNone(cam)
        self.assertEqual(cam.ip, CAM_IP)
        self.assertEqual(cam.mac, FAKE_MAC)  # from the onvif://.../MAC/ scope
        self.assertEqual(cam.model, "I81EM")
        self.assertIsNone(cam.serial)
        self.assertIsNone(cam.dhcp)
        self.assertEqual(cam.sources, {"ONVIF"})

    def test_reply_without_mac_scope_is_still_a_camera(self):
        cam = cd.parse_onvif_reply(ONVIF_NO_MAC_REPLY, "192.168.1.108")
        self.assertIsNotNone(cam)
        self.assertIsNone(cam.mac)
        self.assertEqual(cam.model, "IPC-HDW2431T")  # hardware scope beats name

    def test_name_scope_is_unquoted_fallback(self):
        reply = ONVIF_NO_MAC_REPLY.replace(b"onvif://www.onvif.org/hardware/IPC-HDW2431T", b"")
        self.assertEqual(cd.parse_onvif_reply(reply, "192.168.1.108").model, "Dahua IPC")

    def test_printer_is_not_a_camera(self):
        self.assertIsNone(cd.parse_onvif_reply(PRINTER_REPLY, "192.168.171.40"))

    def test_own_probe_echo_is_not_a_camera(self):
        self.assertIsNone(cd.parse_onvif_reply(cd.build_onvif_probe(), CAM_IP))

    def test_sadp_reply_is_not_onvif(self):
        self.assertIsNone(cd.parse_onvif_reply(SADP_REPLY, CAM_IP))


class TestParseReply(unittest.TestCase):

    def test_dispatches_by_content(self):
        self.assertEqual(cd.parse_reply(SADP_REPLY, CAM_IP).sources, {"SADP"})
        self.assertEqual(cd.parse_reply(ONVIF_REPLY, CAM_IP).sources, {"ONVIF"})

    def test_junk_is_ignored(self):
        for data in (b"", b"\x00\xff garbage", b"<not-closed", b"<ProbeMatch></ProbeMatch>",
                     b"<?xml version='1.0'?><Other/>"):
            with self.subTest(data=data):
                self.assertIsNone(cd.parse_reply(data, CAM_IP))


class TestNormaliseMac(unittest.TestCase):

    def test_formats(self):
        for value in ("24-48-45-AB-CD-EF", "24:48:45:ab:cd:ef", "244845abcdef",
                      " 24:48:45:AB:CD:EF "):
            with self.subTest(value=value):
                self.assertEqual(cd.normalise_mac(value), "24:48:45:ab:cd:ef")

    def test_invalid(self):
        for value in (None, "", "24:48:45:00:00", "zz:48:45:00:00:01", "24:48:45:00:00:01:00"):
            with self.subTest(value=value):
                self.assertIsNone(cd.normalise_mac(value))


class TestMerge(unittest.TestCase):

    def test_sadp_and_onvif_from_one_camera_become_one_row(self):
        merged = cd.merge([cd.parse_onvif_reply(ONVIF_REPLY, CAM_IP),
                           cd.parse_sadp_reply(SADP_REPLY, CAM_IP)])
        self.assertEqual(len(merged), 1)
        cam = merged[0]
        self.assertEqual(cam.sources, {"SADP", "ONVIF"})
        self.assertEqual(cam.sources_label, "ONVIF + SADP")
        self.assertEqual(cam.mac, FAKE_MAC)
        self.assertEqual(cam.serial, "TEST0000000000000000000000")  # filled in from SADP
        self.assertIs(cam.dhcp, True)

    def test_duplicates_collapse_and_rows_sort_numerically(self):
        merged = cd.merge([
            DiscoveredCamera(ip="192.168.1.20", sources={"ONVIF"}),
            DiscoveredCamera(ip="192.168.1.3", sources={"ONVIF"}),
            DiscoveredCamera(ip="192.168.1.20", sources={"ONVIF"}),
        ])
        self.assertEqual([c.ip for c in merged], ["192.168.1.3", "192.168.1.20"])

    def test_merge_does_not_mutate_inputs(self):
        first = DiscoveredCamera(ip=CAM_IP, sources={"ONVIF"})
        cd.merge([first, DiscoveredCamera(ip=CAM_IP, mac=FAKE_MAC, sources={"SADP"})])
        self.assertEqual(first.sources, {"ONVIF"})
        self.assertIsNone(first.mac)


class TestEntryHelpers(unittest.TestCase):

    def test_replace_host(self):
        cases = [
            ("192.168.0.101", "10.0.0.5", "10.0.0.5"),
            ("192.168.0.101:8554", "10.0.0.5", "10.0.0.5:8554"),
            ("  192.168.0.101:554  ", "10.0.0.5", "10.0.0.5:554"),
            ("", "10.0.0.5", "10.0.0.5"),
            ("camera.lan:554", "10.0.0.5", "10.0.0.5:554"),
            ("camera.lan:abc", "10.0.0.5", "10.0.0.5"),  # not a port
        ]
        for entry, new, expected in cases:
            with self.subTest(entry=entry):
                self.assertEqual(cd.replace_host(entry, new), expected)

    def test_entry_host(self):
        self.assertEqual(cd.entry_host("192.168.0.101:8554"), "192.168.0.101")
        self.assertEqual(cd.entry_host(" 192.168.0.101 "), "192.168.0.101")
        self.assertEqual(cd.entry_host(""), "")


class TestLocalIpv4Addresses(unittest.TestCase):

    @staticmethod
    def _infos(*ips):
        return [(socket.AF_INET, socket.SOCK_DGRAM, 17, "", (ip, 0)) for ip in ips]

    def test_drops_loopback_link_local_and_duplicates(self):
        infos = self._infos("127.0.0.1", "169.254.52.251", "192.168.171.26",
                            "100.117.82.113", "192.168.171.26")
        with mock.patch.object(cd.socket, "getaddrinfo", return_value=infos):
            self.assertEqual(cd.local_ipv4_addresses(), ["192.168.171.26", "100.117.82.113"])

    def test_falls_back_to_default_route(self):
        with mock.patch.object(cd.socket, "getaddrinfo", side_effect=OSError("no name")), \
                mock.patch.object(cd, "_default_route_ip", return_value="192.168.171.26"):
            self.assertEqual(cd.local_ipv4_addresses(), ["192.168.171.26"])


class TestMatchConfigured(unittest.TestCase):
    OLD_IP, NEW_IP = "192.168.171.22", "192.168.171.35"
    MINE, OTHER = "24:48:45:00:00:01", "24:48:45:00:00:02"

    def test_no_saved_mac_matches_by_ip(self):
        cams = [DiscoveredCamera(ip=self.OLD_IP, mac=self.OTHER)]
        self.assertEqual(cd.match_configured(cams, self.OLD_IP, ""), (cams[0], False))
        self.assertEqual(cd.match_configured(cams, "10.0.0.1", None), (None, False))

    def test_saved_mac_at_configured_ip(self):
        cams = [DiscoveredCamera(ip=self.OLD_IP, mac=self.MINE)]
        self.assertEqual(cd.match_configured(cams, self.OLD_IP, self.MINE), (cams[0], False))

    def test_camera_moved_and_old_ip_reused_by_another_device(self):
        # The DHCP case this exists for: the old address now belongs to someone else.
        other = DiscoveredCamera(ip=self.OLD_IP, mac=self.OTHER)
        mine = DiscoveredCamera(ip=self.NEW_IP, mac=self.MINE)
        self.assertEqual(cd.match_configured([other, mine], self.OLD_IP, self.MINE),
                         (mine, True))

    def test_saved_mac_absent_and_old_ip_is_a_different_camera(self):
        cams = [DiscoveredCamera(ip=self.OLD_IP, mac=self.OTHER)]
        self.assertEqual(cd.match_configured(cams, self.OLD_IP, self.MINE), (None, False))

    def test_camera_at_configured_ip_with_unknown_mac_still_counts(self):
        cams = [DiscoveredCamera(ip=self.OLD_IP, mac=None)]
        self.assertEqual(cd.match_configured(cams, self.OLD_IP, self.MINE), (cams[0], False))

    def test_saved_mac_format_does_not_matter(self):
        mine = DiscoveredCamera(ip=self.NEW_IP, mac=self.MINE)
        self.assertEqual(cd.match_configured([mine], self.OLD_IP, "24-48-45-00-00-01"),
                         (mine, True))


class TestLookupMac(unittest.TestCase):

    def test_returns_normalised_mac(self):
        with mock.patch.object(cd, "_send_arp", return_value=bytes.fromhex("244845000001")) as arp:
            self.assertEqual(cd.lookup_mac("192.168.171.22:554"), "24:48:45:00:00:01")
        arp.assert_called_once_with("192.168.171.22")  # port stripped

    def test_nothing_usable_gives_none(self):
        # Off-network (None), this PC's own address (b""), an incomplete entry (zeros).
        for raw in (None, b"", bytes(6), b"\x01\x02\x03"):
            with self.subTest(raw=raw), mock.patch.object(cd, "_send_arp", return_value=raw):
                self.assertIsNone(cd.lookup_mac("192.168.171.22"))

    def test_arp_failure_gives_none(self):
        with mock.patch.object(cd, "_send_arp", side_effect=OSError("boom")):
            self.assertIsNone(cd.lookup_mac("192.168.171.22"))

    def test_skips_empty_loopback_and_unresolvable_hosts(self):
        with mock.patch.object(cd, "_send_arp") as arp:
            self.assertIsNone(cd.lookup_mac(""))
            self.assertIsNone(cd.lookup_mac("127.0.0.1"))
            with mock.patch.object(cd.socket, "gethostbyname", side_effect=OSError("no such host")):
                self.assertIsNone(cd.lookup_mac("camera.invalid"))
        arp.assert_not_called()

    def test_windows_only(self):
        with mock.patch.object(cd.sys, "platform", "linux"), \
                mock.patch.object(cd, "_send_arp") as arp:
            self.assertIsNone(cd.lookup_mac("192.168.171.22"))
        arp.assert_not_called()


class _FakeCamera:
    """A UDP 'camera' on 127.0.0.1 that answers the probes with the given replies
    (the real fixtures by default; None = don't answer that protocol)."""

    def __init__(self, sadp=SADP_REPLY, onvif=ONVIF_REPLY):
        self.replies = {"sadp": sadp, "onvif": onvif}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.1)
        self.port = self.sock.getsockname()[1]
        self.probes = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self):
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(65535)
            except (socket.timeout, OSError):
                continue
            self.probes.append(data)
            kind = ("sadp" if b"<Types>inquiry</Types>" in data
                    else "onvif" if b"NetworkVideoTransmitter" in data else None)
            if kind and self.replies[kind]:
                self.sock.sendto(self.replies[kind], addr)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(2)
        self.sock.close()


class TestDiscoverLoop(unittest.TestCase):
    """The whole send/collect loop, aimed at a fake camera instead of multicast."""

    def test_finds_and_merges_fake_camera(self):
        with _FakeCamera() as cam:
            targets = [("SADP", "127.0.0.1", cam.port), ("ONVIF", "127.0.0.1", cam.port)]
            start = time.monotonic()
            found = cd.discover(timeout=1.0, interfaces=["127.0.0.1"], targets=targets)
            elapsed = time.monotonic() - start
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].ip, "127.0.0.1")
        self.assertEqual(found[0].sources, {"SADP", "ONVIF"})
        self.assertEqual(found[0].mac, FAKE_MAC)
        self.assertLess(elapsed, 2.0)
        # Each probe went out twice (UDP repeat), and only those two kinds.
        self.assertEqual(len(cam.probes), 4)

    def test_missing_mac_is_filled_from_arp(self):
        # Most non-Hikvision ONVIF replies carry no MAC; the ARP table has it.
        with _FakeCamera(sadp=None, onvif=ONVIF_NO_MAC_REPLY) as cam, \
                mock.patch.object(cd, "lookup_mac", return_value="aa:bb:cc:dd:ee:ff") as lookup:
            targets = [("SADP", "127.0.0.1", cam.port), ("ONVIF", "127.0.0.1", cam.port)]
            found = cd.discover(timeout=0.6, interfaces=["127.0.0.1"], targets=targets)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].mac, "aa:bb:cc:dd:ee:ff")
        lookup.assert_called_once_with("127.0.0.1")

    def test_mac_from_the_reply_is_not_looked_up(self):
        with _FakeCamera() as cam, mock.patch.object(cd, "lookup_mac") as lookup:
            targets = [("SADP", "127.0.0.1", cam.port), ("ONVIF", "127.0.0.1", cam.port)]
            cd.discover(timeout=0.6, interfaces=["127.0.0.1"], targets=targets)
        lookup.assert_not_called()

    def test_quiet_network_returns_empty(self):
        # A closed port: Windows reports ICMP port-unreachable as WSAECONNRESET
        # on the next recv, which must not count as a reply or an error.
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
        probe.close()
        targets = [("SADP", "127.0.0.1", closed_port), ("ONVIF", "127.0.0.1", closed_port)]
        start = time.monotonic()
        found = cd.discover(timeout=0.5, interfaces=["127.0.0.1"], targets=targets)
        self.assertEqual(found, [])
        self.assertLess(time.monotonic() - start, 1.5)

    def test_no_usable_interface_raises(self):
        with self.assertRaises(cd.DiscoveryError):
            cd.discover(timeout=0.2, interfaces=[])
        with self.assertRaises(cd.DiscoveryError):
            # 203.0.113.0/24 is TEST-NET-3: never a local address, so bind() fails.
            cd.discover(timeout=0.2, interfaces=["203.0.113.5"])


if __name__ == "__main__":
    unittest.main()
