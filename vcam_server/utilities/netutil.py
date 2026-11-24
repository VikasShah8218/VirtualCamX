import ipaddress
import random
import socket

import psutil


def detect_host_ip() -> str:
    """The IP of the NIC that holds the default route (no packet is actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def local_ip_towards(remote_ip: str) -> str | None:
    """The local IP the OS would use to reach `remote_ip` (used for WS-Discovery XAddrs)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((remote_ip, 3702))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def list_nics() -> list[dict]:
    out = []
    stats = psutil.net_if_stats()
    for name, addrs in psutil.net_if_addrs().items():
        ipv4 = [a for a in addrs if a.family == socket.AF_INET]
        mac = next((a.address for a in addrs if a.family == psutil.AF_LINK), None)
        for a in ipv4:
            out.append(
                {
                    "name": name,
                    "ip": a.address,
                    "netmask": a.netmask,
                    "mac": mac,
                    "up": bool(stats.get(name) and stats[name].isup),
                }
            )
    return out


def is_tcp_port_free(port: int, host: str = "0.0.0.0") -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def make_listen_socket(host: str, port: int) -> socket.socket:
    """Create a bound, listening TCP socket. Raises OSError with a clear message on failure."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: never share a camera port by accident
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(128)
        s.setblocking(False)
        return s
    except OSError:
        s.close()
        raise


def random_mac() -> str:
    """Locally administered, unicast MAC (second hex digit 2/6/A/E)."""
    first = (random.randint(0, 255) & 0xFC) | 0x02
    rest = [random.randint(0, 255) for _ in range(5)]
    return ":".join(f"{b:02X}" for b in [first, *rest])


def ip_range(spec: str) -> list[str]:
    lo, hi = spec.split("-")
    a, b = int(ipaddress.IPv4Address(lo.strip())), int(ipaddress.IPv4Address(hi.strip()))
    return [str(ipaddress.IPv4Address(i)) for i in range(a, b + 1)]
