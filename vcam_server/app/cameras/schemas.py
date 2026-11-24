from typing import Any, Literal

from pydantic import BaseModel, Field

from app.cameras.state import SourceSpec


class CameraCreate(BaseModel):
    name: str | None = None
    template_key: str = "bullet_2mp"
    source: SourceSpec | None = None
    stream_mode: Literal["encode", "passthrough"] = "encode"
    http_port: int | None = None
    ip: str | None = None
    username: str | None = None
    password: str | None = None
    enabled: bool = True


class BulkCreate(BaseModel):
    count: int = Field(ge=1, le=1000)
    template_key: str = "bullet_2mp"
    name_pattern: str = "VCam-{n:03d}"
    first_index: int | None = None
    source: SourceSpec | None = None
    spread_paths: list[str] | None = None  # one file per camera, round-robin
    offset_step_s: float = 0.0  # start offset grows by this per camera
    stream_mode: Literal["encode", "passthrough"] = "encode"
    start_port: int | None = None
    username: str | None = None
    password: str | None = None


class CameraPatch(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    http_port: int | None = None


class SourceIn(BaseModel):
    source: SourceSpec
    stream_mode: Literal["encode", "passthrough"] | None = None


class BulkSourceIn(BaseModel):
    ids: list[int]
    source: SourceSpec | None = None
    spread_paths: list[str] | None = None
    offset_step_s: float = 0.0
    stream_mode: Literal["encode", "passthrough"] | None = None


class BulkAction(BaseModel):
    ids: list[int]
    action: Literal["start", "stop", "restart", "reboot", "delete", "enable", "disable"]
    params: dict[str, Any] = Field(default_factory=dict)


class CameraUserIn(BaseModel):
    username: str
    password: str
    level: Literal["Administrator", "Operator", "User"] = "User"


class CameraUserPatch(BaseModel):
    password: str | None = None
    level: Literal["Administrator", "Operator", "User"] | None = None
