"""ONVIF Inspector: in-memory ring buffer of every ONVIF request/response per camera."""
import itertools
import time
from collections import deque
from dataclasses import asdict, dataclass

from app.system import hub
from settings.settings import settings

MAX_XML = 64 * 1024
_seq = itertools.count(1)
_buffers: dict[int, deque] = {}


@dataclass
class InspectorEntry:
    id: int
    camera_id: int
    ts: float
    client_ip: str
    path: str
    service: str
    operation: str
    user: str | None
    auth: str  # ok | failed | none | pre_auth
    auth_method: str
    status: int
    duration_ms: float
    fault: str | None
    request_xml: str
    response_xml: str

    def summary(self) -> dict:
        d = asdict(self)
        d.pop("request_xml")
        d.pop("response_xml")
        return d


def _clip(data: bytes | str) -> str:
    s = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    return s if len(s) <= MAX_XML else s[:MAX_XML] + "\n<!-- truncated -->"


def record(camera_id: int, **kw) -> InspectorEntry:
    entry = InspectorEntry(
        id=next(_seq),
        camera_id=camera_id,
        ts=time.time(),
        request_xml=_clip(kw.pop("request_xml", b"")),
        response_xml=_clip(kw.pop("response_xml", b"")),
        **kw,
    )
    buf = _buffers.setdefault(camera_id, deque(maxlen=settings.inspector_buffer_per_camera))
    buf.append(entry)
    hub.publish("inspector", entry.summary())
    return entry


def query(camera_id: int | None = None, operation: str | None = None, client_ip: str | None = None,
          since_id: int = 0, limit: int = 200) -> list[dict]:
    sources = [_buffers.get(camera_id, deque())] if camera_id is not None else list(_buffers.values())
    rows = [e for buf in sources for e in buf if e.id > since_id]
    if operation:
        rows = [e for e in rows if operation.lower() in e.operation.lower()]
    if client_ip:
        rows = [e for e in rows if e.client_ip == client_ip]
    rows.sort(key=lambda e: e.id, reverse=True)
    return [e.summary() for e in rows[:limit]]


def get(entry_id: int) -> InspectorEntry | None:
    for buf in _buffers.values():
        for e in buf:
            if e.id == entry_id:
                return e
    return None


def clear(camera_id: int | None = None) -> None:
    if camera_id is None:
        _buffers.clear()
    else:
        _buffers.pop(camera_id, None)


def clients(camera_id: int) -> list[dict]:
    """Distinct ONVIF clients seen for a camera (which NVRs talk to it)."""
    seen: dict[str, dict] = {}
    for e in _buffers.get(camera_id, ()):
        c = seen.setdefault(e.client_ip, {"client_ip": e.client_ip, "requests": 0, "last_seen": 0.0, "users": set()})
        c["requests"] += 1
        c["last_seen"] = max(c["last_seen"], e.ts)
        if e.user:
            c["users"].add(e.user)
    return [{**c, "users": sorted(c["users"])} for c in seen.values()]
