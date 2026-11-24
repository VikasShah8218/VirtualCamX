"""Response models for the Manager API.

They exist so the generated TypeScript types (vcam_client: `npm run gen:api`) describe the real
payloads instead of `unknown`. Keep them in sync with CameraRuntime.info() and friends.
"""
from typing import Any

from app.cameras.state import BaseModel, Identity, SourceSpec


class StreamSummary(BaseModel):
    key: str
    encoding: str
    width: int
    height: int
    fps: int
    bitrate_kbps: int


class CameraUrls(BaseModel):
    onvif: str
    web: str
    rtsp: dict[str, str]
    snapshot: dict[str, str]


class WorkerInfo(BaseModel):
    status: str
    pid: int | None = None
    mode: str | None = None
    input: str | None = None
    started_at: float | None = None
    restarts: int = 0
    last_error: str | None = None
    stderr_tail: list[str] = []


class FaultOut(BaseModel):
    id: int
    type: str
    params: dict[str, Any]
    started_at: str
    expires_at: str | None = None


class CameraOut(BaseModel):
    id: int
    number: int
    name: str
    enabled: bool
    template_key: str
    status: str
    last_error: str | None = None
    addr_mode: str
    ip: str
    http_port: int
    boot_time: str | None = None
    source: SourceSpec
    stream_mode: str
    streams: list[StreamSummary]
    urls: CameraUrls
    worker: WorkerInfo
    faults: list[FaultOut]
    subscriptions: int
    has_ptz: bool
    identity: Identity


class CameraListOut(BaseModel):
    items: list[CameraOut]
    total: int


class BulkCreatedOut(BaseModel):
    created: list[CameraOut]


class ResultsOut(BaseModel):
    """Per-camera results of a bulk operation: {camera_id: "ok" | error message}."""

    results: dict[int, str]


class OkOut(BaseModel):
    ok: bool = True


class RtspSession(BaseModel):
    id: str | None = None
    created: str | None = None
    remoteAddr: str | None = None
    path: str | None = None
    transport: str | None = None
    bytesSent: int | None = None


class OnvifClient(BaseModel):
    client_ip: str
    requests: int
    last_seen: float
    users: list[str]


class SubscriptionOut(BaseModel):
    id: str
    kind: str
    termination: str
    consumer: str | None = None
    queued: int


class ClientsOut(BaseModel):
    rtsp: list[RtspSession]
    onvif: list[OnvifClient]
    subscriptions: list[SubscriptionOut]


class LogOut(BaseModel):
    lines: list[str]


class CameraUserOut(BaseModel):
    username: str
    level: str
