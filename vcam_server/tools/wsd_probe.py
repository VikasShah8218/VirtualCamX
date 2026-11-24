"""Send a WS-Discovery Probe (like an NVR's "search cameras" button) and list who answers.

    py tools/wsd_probe.py [seconds] [interface_ip]
"""
import socket
import sys
import time
import uuid

from lxml import etree

PROBE = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
<s:Header><a:Action s:mustUnderstand="1">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action>
<a:MessageID>uuid:{mid}</a:MessageID><a:To s:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To></s:Header>
<s:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></s:Body></s:Envelope>"""


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    iface = sys.argv[2] if len(sys.argv) > 2 else None
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    if iface:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface))
    s.bind((iface or "", 0))
    s.settimeout(0.3)
    s.sendto(PROBE.format(mid=uuid.uuid4()).encode(), ("239.255.255.250", 3702))
    found = {}
    end = time.time() + seconds
    while time.time() < end:
        try:
            data, addr = s.recvfrom(65535)
        except socket.timeout:
            continue
        root = etree.fromstring(data)
        for m in root.iter("{http://schemas.xmlsoap.org/ws/2005/04/discovery}ProbeMatch"):
            epr = m.findtext(".//{*}Address")
            xaddrs = m.findtext("{*}XAddrs")
            scopes = (m.findtext("{*}Scopes") or "").split()
            name = next((x.rsplit("/", 1)[-1] for x in scopes if "/name/" in x), "?")
            hw = next((x.rsplit("/", 1)[-1] for x in scopes if "/hardware/" in x), "?")
            found[epr] = (name, hw, xaddrs, addr[0])
    for epr, (name, hw, xaddrs, src) in sorted(found.items(), key=lambda kv: kv[1][2]):
        print(f"{name:<20} {hw:<14} {xaddrs}   (from {src}, {epr})")
    print(f"{len(found)} device(s) answered")


if __name__ == "__main__":
    main()
