"""CameraState: the full configuration of one virtual camera (the "camera document").

ONVIF, the camera web API and the Manager API all read and write this one document.
It is stored as JSON in Camera.state. See plan/BACKEND_IMPLEMENTATION_PLAN.md section 4.2.
"""
from typing import Literal

from pydantic import BaseModel as _PydanticModel
from pydantic import ConfigDict, Field


class BaseModel(_PydanticModel):
    # Fields with defaults are always present in responses: say so in the OpenAPI schema, so the
    # generated TypeScript types (vcam_client) do not mark them optional.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

Encoding = Literal["H264", "H265", "JPEG"]
StreamKey = Literal["main", "sub", "third"]


class Identity(BaseModel):
    manufacturer: str = "VirtualCamX"
    model: str = "VCX-IPC-2MP"
    firmware_version: str = "V1.0.0 build 261123"
    serial_number: str = ""
    hardware_id: str = "VCX-HW-1"
    mac: str = ""
    endpoint_uuid: str = ""


class NetworkState(BaseModel):
    hostname: str = ""
    hostname_from_dhcp: bool = False
    dhcp: bool = False
    reported_ip: str | None = None  # set via ONVIF SetNetworkInterfaces; reported only
    prefix_length: int = 24
    gateway: str = "192.168.1.1"
    dns_from_dhcp: bool = False
    dns: list[str] = Field(default_factory=lambda: ["8.8.8.8"])
    ntp_from_dhcp: bool = False
    ntp: list[str] = Field(default_factory=lambda: ["pool.ntp.org"])
    discovery_mode: Literal["Discoverable", "NonDiscoverable"] = "Discoverable"
    http_enabled: bool = True
    rtsp_enabled: bool = True
    mtu: int = 1500


class TimeState(BaseModel):
    date_time_type: Literal["NTP", "Manual"] = "NTP"
    tz: str = "UTC0"  # POSIX TZ string, as ONVIF uses
    daylight_savings: bool = False
    offset_seconds: float = 0.0  # camera clock = host UTC + offset


class SourceSpec(BaseModel):
    type: Literal["test_pattern", "file", "image", "rtsp"] = "test_pattern"
    path: str | None = None  # file or image path on the VirtualCamX host
    url: str | None = None  # rtsp relay
    pattern: Literal["testsrc2", "smptehdbars", "mandelbrot"] = "testsrc2"
    start_offset: float = 0.0
    loop: bool = True


class VideoSource(BaseModel):
    token: str = "VideoSource_1"
    width: int = 1920
    height: int = 1080
    framerate: float = 25.0


class VideoSourceConfig(BaseModel):
    token: str = "VideoSourceConfig_1"
    name: str = "VideoSourceConfig_1"
    source_token: str = "VideoSource_1"
    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080


class VideoEncoderConfig(BaseModel):
    token: str
    name: str
    stream_key: StreamKey
    encoding: Encoding = "H264"
    width: int = 1920
    height: int = 1080
    quality: float = 6.0  # 1..10
    fps: int = 25
    bitrate_kbps: int = 4096
    rc_mode: Literal["CBR", "VBR"] = "CBR"
    gov_length: int = 50
    h264_profile: Literal["Baseline", "Main", "High"] = "Main"
    multicast_address: str = "0.0.0.0"
    multicast_port: int = 0
    multicast_ttl: int = 1
    session_timeout_s: int = 60


class PtzConfigModel(BaseModel):
    token: str = "PTZConfig_1"
    name: str = "PTZConfig_1"
    node_token: str = "PTZNode_1"
    default_timeout_s: int = 5
    default_pan_tilt_speed: float = 0.5
    default_zoom_speed: float = 0.5


class MediaProfile(BaseModel):
    token: str
    name: str
    fixed: bool = True
    vsc_token: str | None = "VideoSourceConfig_1"
    vec_token: str | None = None
    ptz_token: str | None = None


class ImagingSettings(BaseModel):
    brightness: float = 50.0  # 0..100
    color_saturation: float = 50.0
    contrast: float = 50.0
    sharpness: float = 50.0
    ir_cut: Literal["ON", "OFF", "AUTO"] = "AUTO"  # OFF = night (grayscale)
    wdr_mode: Literal["ON", "OFF"] = "OFF"
    wdr_level: float = 50.0
    backlight: Literal["ON", "OFF"] = "OFF"
    exposure_mode: Literal["AUTO", "MANUAL"] = "AUTO"
    white_balance: Literal["AUTO", "MANUAL"] = "AUTO"
    focus_mode: Literal["AUTO", "MANUAL"] = "AUTO"
    mirror: bool = False
    flip: bool = False


class OsdItem(BaseModel):
    token: str
    kind: Literal["DateAndTime", "Plain", "Date", "Time"] = "Plain"
    plain_text: str = ""
    position: Literal["UpperLeft", "UpperRight", "LowerLeft", "LowerRight", "Custom"] = "UpperLeft"
    x: float = -1.0  # Custom position, ONVIF normalized -1..1
    y: float = 1.0
    font_size: int = 32
    date_format: str = "yyyy-MM-dd"
    time_format: str = "HH:mm:ss"
    enabled: bool = True


class PtzPreset(BaseModel):
    token: str
    name: str
    pan: float = 0.0
    tilt: float = 0.0
    zoom: float = 0.0


class PtzState(BaseModel):
    presets: list[PtzPreset] = Field(default_factory=list)
    home_pan: float = 0.0
    home_tilt: float = 0.0
    home_zoom: float = 0.0
    max_presets: int = 256


class DigitalInput(BaseModel):
    token: str
    idle_state: Literal["closed", "open"] = "open"
    active: bool = False


class RelayOutput(BaseModel):
    token: str
    mode: Literal["Bistable", "Monostable"] = "Bistable"
    delay_time_s: int = 5
    idle_state: Literal["closed", "open"] = "open"
    active: bool = False


class IoState(BaseModel):
    inputs: list[DigitalInput] = Field(default_factory=list)
    relays: list[RelayOutput] = Field(default_factory=list)


class MotionConfig(BaseModel):
    enabled: bool = True
    sensitivity: int = 50
    area: list[list[float]] = Field(default_factory=list)  # stored only


class SecurityState(BaseModel):
    auth_mode: Literal["both", "wsse", "digest"] = "both"
    allow_password_text: bool = True
    allow_basic: bool = False
    snapshot_auth: bool = True


class StreamOptions(BaseModel):
    """What a stream slot is allowed to be set to (from the template)."""

    resolutions: list[tuple[int, int]]
    encodings: list[Encoding] = Field(default_factory=lambda: ["H264", "H265", "JPEG"])
    max_fps: int = 30
    bitrate_min_kbps: int = 64
    bitrate_max_kbps: int = 16384


class Capabilities(BaseModel):
    has_ptz: bool = False
    has_audio: bool = False
    max_profiles: int = 6
    max_osd: int = 4
    stream_options: dict[str, StreamOptions] = Field(default_factory=dict)  # by stream key


class CameraState(BaseModel):
    identity: Identity = Field(default_factory=Identity)
    network: NetworkState = Field(default_factory=NetworkState)
    time: TimeState = Field(default_factory=TimeState)
    scopes: list[str] = Field(default_factory=list)
    source: SourceSpec = Field(default_factory=SourceSpec)
    stream_mode: Literal["passthrough", "encode"] = "encode"
    video_source: VideoSource = Field(default_factory=VideoSource)
    video_source_configs: list[VideoSourceConfig] = Field(default_factory=lambda: [VideoSourceConfig()])
    video_encoders: list[VideoEncoderConfig] = Field(default_factory=list)
    ptz_configs: list[PtzConfigModel] = Field(default_factory=list)
    profiles: list[MediaProfile] = Field(default_factory=list)
    imaging: ImagingSettings = Field(default_factory=ImagingSettings)
    osd: list[OsdItem] = Field(default_factory=list)
    osd_show_events: bool = True
    ptz: PtzState = Field(default_factory=PtzState)
    io: IoState = Field(default_factory=IoState)
    motion: MotionConfig = Field(default_factory=MotionConfig)
    security: SecurityState = Field(default_factory=SecurityState)
    capabilities: Capabilities = Field(default_factory=Capabilities)

    # ---- lookups ---------------------------------------------------------------------------
    def encoder(self, token: str) -> VideoEncoderConfig | None:
        return next((e for e in self.video_encoders if e.token == token), None)

    def encoder_by_key(self, key: str) -> VideoEncoderConfig | None:
        return next((e for e in self.video_encoders if e.stream_key == key), None)

    def profile(self, token: str) -> MediaProfile | None:
        return next((p for p in self.profiles if p.token == token), None)

    def vsc(self, token: str) -> VideoSourceConfig | None:
        return next((c for c in self.video_source_configs if c.token == token), None)

    def ptz_config(self, token: str) -> PtzConfigModel | None:
        return next((c for c in self.ptz_configs if c.token == token), None)

    def use_count(self, kind: str, token: str) -> int:
        attr = {"vsc": "vsc_token", "vec": "vec_token", "ptz": "ptz_token"}[kind]
        return sum(1 for p in self.profiles if getattr(p, attr) == token)
