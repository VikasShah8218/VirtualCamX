"""WS-Discovery responder (UDP 3702, multicast 239.255.255.250) for all virtual cameras.

One ProbeMatches message per camera (some NVRs only read the first match of a message),
each sent unicast to the prober after a random 0..500 ms delay (APP_MAX_DELAY).
"""
import asyncio
import logging
import random
import socket
import struct
import uuid
from typing import TYPE_CHECKING

from lxml import etree

from app.onvif import namespaces as NS
from app.onvif.xml import child, el, local, text
from utilities.netutil import local_ip_towards

if TYPE_CHECKING:
    from app.runtime.camera_runtime import CameraRuntime
    from app.runtime.manager import CameraManager

logger = logging.getLogger("vcam.wsd")

MCAST_GRP = "239.255.255.250"
MCAST_PORT = 3702
APP_MAX_DELAY = 0.5
TYPES = "dn:NetworkVideoTransmitter tds:Device"
_DECLS = (
    f'xmlns:s="{NS.SOAP12}" xmlns:a="{NS.WSA_2004}" xmlns:d="{NS.WSD}" '
    f'xmlns:dn="{NS.NETWORK}" xmlns:tds="{NS.DEVICE}"'
)
_parser = etree.XMLParser(resolve_entities=False, no_network=True)
KNOWN_TYPES = {(NS.NETWORK, "NetworkVideoTransmitter"), (NS.DEVICE, "Device")}


def _envelope(action: str, body: str, relates_to: str | None = None, to: str | None = None, seq: str = "") -> bytes:
    header = el("a:MessageID", f"uuid:{uuid.uuid4()}")
    if relates_to:
        header += el("a:RelatesTo", relates_to)
    header += el("a:To", to or "http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous")
    header += el("a:Action", action) + seq
    return f'<?xml version="1.0" encoding="UTF-8"?><s:Envelope {_DECLS}><s:Header>{header}</s:Header><s:Body>{body}</s:Body></s:Envelope>'.encode()


def scope_matches(requested: list[str], scopes: list[str]) -> bool:
    """RFC 3986 rule: every requested scope must be a segment-wise prefix of some camera scope."""
    def segs(s: str) -> list[str]:
        return [p for p in s.strip().rstrip("/").split("/") if p]

    for r in requested:
        rs = segs(r)
        if not any(segs(s)[: len(rs)] == rs for s in scopes):
            return False
    return True


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, owner: "WsDiscovery"):
        self.owner = owner

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            self.owner.on_datagram(data, addr)
        except Exception:
            logger.exception("bad WS-Discovery datagram from %s", addr)


class WsDiscovery:
    def __init__(self, manager: "CameraManager", interface_ip: str):
        self.manager = manager
        self.interface_ip = interface_ip
        self.transport: asyncio.DatagramTransport | None = None
        self.instance_id = random.randint(1, 2**31)
        self.msg_no = 0
        self.error: str | None = None
        self.probes_seen = 0

    async def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", MCAST_PORT))
            mreq = struct.pack("4s4s", socket.inet_aton(MCAST_GRP), socket.inet_aton(self.interface_ip or "0.0.0.0"))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            if self.interface_ip:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.interface_ip))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        except OSError as exc:
            sock.close()
            self.error = (
                f"WS-Discovery could not bind UDP {MCAST_PORT}: {exc}. Cameras still work when added by IP:port. "
                "On Windows, the 'Function Discovery Provider Host' service may hold this port."
            )
            logger.error(self.error)
            return
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(lambda: _Protocol(self), sock=sock)
        logger.info("WS-Discovery listening on UDP %s (interface %s)", MCAST_PORT, self.interface_ip or "default")

    def stop(self) -> None:
        if self.transport:
            for rt in self.manager.all():
                self.bye(rt)
            self.transport.close()
            self.transport = None

    # ---- messages -----------------------------------------------------------------------------
    def _seq(self) -> str:
        self.msg_no += 1
        return el("d:AppSequence", InstanceId=self.instance_id, MessageNumber=self.msg_no)

    def _xaddr(self, rt: "CameraRuntime", towards: str | None) -> str:
        if rt.addr_mode == "ip" and rt.ip:
            host = rt.ip
        else:
            host = (local_ip_towards(towards) if towards else None) or rt.advertised_ip()
            if host.startswith("127.") and towards and not towards.startswith("127."):
                host = rt.advertised_ip()
        port = rt.http_port_public()
        return f"http://{host}{'' if port == 80 else f':{port}'}/onvif/device_service"

    def _match_body(self, tag: str, rt: "CameraRuntime", towards: str | None) -> str:
        st = rt.state
        return el(
            tag,
            el("a:EndpointReference", el("a:Address", f"urn:uuid:{st.identity.endpoint_uuid}")),
            el("d:Types", TYPES),
            el("d:Scopes", " ".join(st.scopes)),
            el("d:XAddrs", self._xaddr(rt, towards)),
            el("d:MetadataVersion", 1),
        )

    def _discoverable(self) -> list["CameraRuntime"]:
        from app.runtime.camera_runtime import CameraStatus

        return [
            rt for rt in self.manager.all()
            if rt.status == CameraStatus.RUNNING and rt.state.network.discovery_mode == "Discoverable"
        ]

    def on_datagram(self, data: bytes, addr) -> None:
        if b"Probe" not in data and b"Resolve" not in data:
            return
        root = etree.fromstring(data, _parser)
        header = child(root, "Header")
        body = child(root, "Body")
        if body is None or len(body) == 0:
            return
        msg = body[0]
        kind = local(msg.tag)
        msg_id = text(header, "MessageID")
        if kind == "Probe":
            self.probes_seen += 1
            types_el = child(msg, "Types")
            req_types = []
            if types_el is not None and types_el.text:
                for qn in types_el.text.split():
                    prefix, _, name = qn.rpartition(":")
                    req_types.append((types_el.nsmap.get(prefix or None, ""), name))
            scopes_el = child(msg, "Scopes")
            req_scopes = scopes_el.text.split() if scopes_el is not None and scopes_el.text else []
            if req_types and not all(t in KNOWN_TYPES for t in req_types):
                return
            for rt in self._discoverable():
                if req_scopes and not scope_matches(req_scopes, rt.state.scopes):
                    continue
                payload = _envelope(
                    "http://schemas.xmlsoap.org/ws/2005/04/discovery/ProbeMatches",
                    el("d:ProbeMatches", self._match_body("d:ProbeMatch", rt, addr[0])),
                    relates_to=msg_id,
                    seq=self._seq(),
                )
                asyncio.get_running_loop().call_later(random.uniform(0, APP_MAX_DELAY), self._send, payload, addr)
        elif kind == "Resolve":
            addr_txt = text(msg, "EndpointReference", "Address") or ""
            for rt in self._discoverable():
                if addr_txt.endswith(rt.state.identity.endpoint_uuid):
                    payload = _envelope(
                        "http://schemas.xmlsoap.org/ws/2005/04/discovery/ResolveMatches",
                        el("d:ResolveMatches", self._match_body("d:ResolveMatch", rt, addr[0])),
                        relates_to=msg_id,
                        seq=self._seq(),
                    )
                    self._send(payload, addr)

    def _send(self, payload: bytes, addr) -> None:
        if self.transport:
            try:
                self.transport.sendto(payload, addr)
            except OSError as exc:
                logger.debug("WS-Discovery send to %s failed: %s", addr, exc)

    def hello(self, rt: "CameraRuntime") -> None:
        if not self.transport or rt.state.network.discovery_mode != "Discoverable":
            return
        payload = _envelope(
            "http://schemas.xmlsoap.org/ws/2005/04/discovery/Hello",
            self._match_body("d:Hello", rt, None),
            to="urn:schemas-xmlsoap-org:ws:2005:04:discovery",
            seq=self._seq(),
        )
        self._send(payload, (MCAST_GRP, MCAST_PORT))

    def bye(self, rt: "CameraRuntime") -> None:
        if not self.transport:
            return
        body = el("d:Bye", el("a:EndpointReference", el("a:Address", f"urn:uuid:{rt.state.identity.endpoint_uuid}")))
        payload = _envelope(
            "http://schemas.xmlsoap.org/ws/2005/04/discovery/Bye", body,
            to="urn:schemas-xmlsoap-org:ws:2005:04:discovery", seq=self._seq(),
        )
        self._send(payload, (MCAST_GRP, MCAST_PORT))
