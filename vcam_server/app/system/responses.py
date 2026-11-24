"""Response models for system, events, faults, inspector, media and templates endpoints."""
from typing import Any, Literal

from app.cameras.state import BaseModel


# ---- system ------------------------------------------------------------------------------------

class FarmStats(BaseModel):
    cameras: int = 0
    running: int = 0
    offline: int = 0
    error: int = 0
    stopped: int = 0
    rtsp_clients: int = 0
    kbps_out: float = 0
    subscriptions: int = 0
    cpu_percent: float = 0
    ram_percent: float = 0
    active_faults: int = 0


class StreamStat(BaseModel):
    ready: bool | None = None
    readers: int = 0
    kbps: float = 0


class CameraStats(BaseModel):
    readers: int = 0
    kbps_in: float = 0
    kbps_out: float = 0
    streams: dict[str, StreamStat] = {}


class StatsOut(BaseModel):
    farm: FarmStats
    cameras: dict[int, CameraStats]


class FfmpegHealth(BaseModel):
    ok: bool = False
    path: str = ""
    version: str = ""
    zmq_filter: bool | None = None
    drawtext: bool | None = None
    libx264: bool | None = None
    libx265: bool | None = None


class MediaMtxHealth(BaseModel):
    running: bool
    restarts: int
    log_tail: list[str]


class WsdHealth(BaseModel):
    running: bool
    error: str | None = None
    probes_seen: int = 0


class HealthOut(BaseModel):
    ffmpeg: FfmpegHealth | None = None
    ffprobe: dict[str, Any] | None = None
    mediamtx: MediaMtxHealth
    ws_discovery: WsdHealth
    host_ip: str
    addr_mode: str
    uptime_s: int


class NicOut(BaseModel):
    name: str
    ip: str
    netmask: str | None = None
    mac: str | None = None
    up: bool


# ---- events -------------------------------------------------------------------------------------

class EventOut(BaseModel):
    id: int
    topic: str
    operation: str
    source: dict[str, Any]
    data: dict[str, Any]
    origin: str
    utc_time: Any


class EventStateOut(BaseModel):
    topic: str
    utc_time: str
    operation: str
    source: dict[str, Any]
    data: dict[str, Any]


class ScheduleOut(BaseModel):
    id: int
    camera_id: int
    kind: Literal["motion", "tamper", "digital_input", "video_loss"]
    token: str | None = None
    mode: Literal["periodic", "random"]
    interval_s: float
    interval_max_s: float
    active_s: float
    enabled: bool
    created_at: Any = None


class IdOut(BaseModel):
    id: int


class CountOut(BaseModel):
    triggered: int | None = None
    cleared: int | None = None
    retried: int | None = None


# ---- faults -------------------------------------------------------------------------------------

class FaultTypeOut(BaseModel):
    label: str
    desc: str
    params: dict[str, Any]


# ---- inspector ----------------------------------------------------------------------------------

class InspectorSummary(BaseModel):
    id: int
    camera_id: int
    ts: float
    client_ip: str
    path: str
    service: str
    operation: str
    user: str | None = None
    auth: str
    auth_method: str
    status: int
    duration_ms: float
    fault: str | None = None


class InspectorEntryOut(InspectorSummary):
    request_xml: str
    response_xml: str


class InspectorListOut(BaseModel):
    items: list[InspectorSummary]


# ---- media --------------------------------------------------------------------------------------

class ProbeVideo(BaseModel):
    codec: str | None = None
    profile: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    pix_fmt: str | None = None


class ProbeAudio(BaseModel):
    codec: str | None = None
    sample_rate: str | None = None
    channels: int | None = None


class ProbeOut(BaseModel):
    path: str
    fingerprint: str
    format: str | None = None
    duration_s: float | None = None
    size_bytes: int = 0
    bitrate_kbps: int | None = None
    video: ProbeVideo
    audio: ProbeAudio | None = None


class FsEntry(BaseModel):
    name: str
    path: str
    kind: str  # dir | video | image | other
    is_dir: bool
    size_bytes: int | None = None


class FsRoot(BaseModel):
    name: str
    path: str
    is_dir: bool


class BrowseOut(BaseModel):
    path: str
    parent: str | None = None
    entries: list[FsEntry]


class MediaItemOut(BaseModel):
    id: int
    path: str
    label: str
    probe: ProbeOut | None = None
    used_by: list[int] = []


class JobOut(BaseModel):
    path: str
    profile_key: str
    status: str
    error: str | None = None
    progress: int = 0


# ---- templates ----------------------------------------------------------------------------------

class TemplateOut(BaseModel):
    key: str
    builtin: bool
    name: str
    model: str
    native: list[int]
    main_res: list[list[int]]
    main: list[Any]
    sub: list[Any] | None = None
    third: list[Any] | None = None
    ptz: bool
    inputs: int
    relays: int
