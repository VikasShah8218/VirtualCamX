"""Operation registry: (namespace, operation) -> handler, plus ONVIF access classes."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from app.onvif import namespaces as NS
from app.onvif.security import UserEntry
from app.onvif.soap import SoapRequest

if TYPE_CHECKING:
    from app.runtime.camera_runtime import CameraRuntime


class Access(IntEnum):
    PRE_AUTH = 0
    READ_SYSTEM = 1
    READ_SYSTEM_SENSITIVE = 2
    READ_SYSTEM_SECRET = 3
    READ_MEDIA = 4
    ACTUATE = 5
    WRITE_SYSTEM = 6
    UNRECOVERABLE = 7


_USER = {Access.PRE_AUTH, Access.READ_SYSTEM, Access.READ_MEDIA}
_OPERATOR = _USER | {Access.READ_SYSTEM_SENSITIVE, Access.ACTUATE}
LEVEL_ALLOWED: dict[str, set[Access]] = {
    "Administrator": set(Access),
    "Operator": _OPERATOR,
    "User": _USER,
    "Anonymous": {Access.PRE_AUTH},
}


@dataclass
class OnvifContext:
    runtime: "CameraRuntime"
    req: SoapRequest
    host: str  # camera IP as the client sees it
    port: int  # camera HTTP port
    path: str
    client_ip: str
    user: UserEntry | None = None
    extra_headers: list[str] = field(default_factory=list)

    @property
    def state(self):
        return self.runtime.state

    @property
    def body(self):
        return self.req.body_el

    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}" if self.port != 80 else f"http://{self.host}"

    def xaddr(self, ns: str) -> str:
        return f"{self.base_url()}/onvif/{NS.SERVICE_PATHS[ns]}"

    def rtsp_url(self, stream_key: str) -> str:
        return self.runtime.rtsp_url(self.host, stream_key)

    def snapshot_url(self, profile_token: str) -> str:
        return f"{self.base_url()}/snapshot/{profile_token}.jpg"


Handler = Callable[[OnvifContext], Awaitable[str]]


@dataclass
class Operation:
    ns: str
    name: str
    access: Access
    func: Handler


REGISTRY: dict[tuple[str, str], Operation] = {}


def onvif_operation(ns: str, name: str, access: Access = Access.READ_SYSTEM):
    def deco(func: Handler) -> Handler:
        REGISTRY[(ns, name)] = Operation(ns, name, access, func)
        return func

    return deco


def find(ns: str, name: str) -> Operation | None:
    return REGISTRY.get((ns, name))


def is_allowed(level: str, access: Access) -> bool:
    return access in LEVEL_ALLOWED.get(level, set())


def load_handlers() -> None:
    """Import all handler modules so their decorators register operations."""
    from app.onvif.handlers import deviceio, device, events, imaging, media, media2, ptz  # noqa: F401
