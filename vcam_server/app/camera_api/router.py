"""/api/cam/v1: backend of the per-camera web page ("real camera" UI).

Logs in with that camera's own users. Cookies are per host (not per port), so the session
cookie name includes the camera id: in Port Mode all cameras share one host.
"""
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from app.cameras import operations as ops
from app.cameras import services as cam_services
from app.cameras import users as user_ops
from app.cameras.state import CameraState, Identity, ImagingSettings, OsdItem, PtzPreset, StreamOptions, VideoEncoderConfig
from app.onvif.faults import OnvifFault
from app.streams.whep import whep_close, whep_offer

router = APIRouter(prefix="/api/cam/v1", tags=["camera-web"])

SESSION_IDLE_S = 30 * 60
_sessions: dict[str, dict] = {}
LEVEL_RANK = {"User": 1, "Operator": 2, "Administrator": 3}


def _cookie_name(camera_id: int) -> str:
    return f"vcxs{camera_id}"


def _camera(request: Request):
    from app.camera_api.app import current_camera

    return current_camera(request)


def _session(request: Request, rt=Depends(_camera)) -> dict:
    token = request.cookies.get(_cookie_name(rt.camera_id))
    auth = request.headers.get("authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth[7:]
    s = _sessions.get(token or "")
    if not s or s["camera_id"] != rt.camera_id or time.time() - s["seen"] > SESSION_IDLE_S:
        raise HTTPException(401, "Login required")
    if s["username"] not in rt.users:
        raise HTTPException(401, "User no longer exists")
    s["seen"] = time.time()
    s["level"] = rt.users[s["username"]].level
    return s


def need(level: str):
    def dep(s: dict = Depends(_session)) -> dict:
        if LEVEL_RANK.get(s["level"], 0) < LEVEL_RANK[level]:
            raise HTTPException(403, f"{level} rights required")
        return s

    return dep


def _fault(exc: OnvifFault) -> HTTPException:
    return HTTPException(422, exc.reason)


class LoginIn(BaseModel):
    username: str
    password: str


class SessionOut(BaseModel):
    username: str
    level: str
    token: str


class CamUser(BaseModel):
    username: str
    level: str


class DeviceOut(BaseModel):
    name: str
    identity: Identity
    status: str
    boot_time: str | None = None
    urls: dict
    has_ptz: bool
    user: CamUser


class StreamsOut(BaseModel):
    encoders: list[VideoEncoderConfig]
    options: dict[str, StreamOptions]


class PtzStatusOut(BaseModel):
    pan: float
    tilt: float
    zoom: float
    moving: bool
    presets: list[PtzPreset]


class LogLines(BaseModel):
    lines: list[str]


@router.post("/login", response_model=SessionOut)
async def login(body: LoginIn, response: Response, rt=Depends(_camera)):
    u = rt.users.get(body.username)
    if not u or not secrets.compare_digest(u.password, body.password) or rt.faults.auth_broken():
        rt.log(f"web login failed for {body.username}")
        raise HTTPException(401, "Wrong username or password")
    token = secrets.token_urlsafe(24)
    _sessions[token] = {"camera_id": rt.camera_id, "username": u.username, "level": u.level, "seen": time.time()}
    response.set_cookie(_cookie_name(rt.camera_id), token, httponly=True, samesite="lax")
    rt.log(f"web login: {u.username}")
    return {"username": u.username, "level": u.level, "token": token}


@router.post("/logout")
async def logout(request: Request, response: Response, rt=Depends(_camera)):
    _sessions.pop(request.cookies.get(_cookie_name(rt.camera_id), ""), None)
    response.delete_cookie(_cookie_name(rt.camera_id))
    return {"ok": True}


@router.get("/device", response_model=DeviceOut)
async def device(s=Depends(_session), rt=Depends(_camera)):
    st = rt.state
    return {
        "name": rt.name,
        "identity": st.identity.model_dump(),
        "status": rt.status.value,
        "boot_time": rt.boot_time.isoformat() if rt.boot_time else None,
        "urls": rt.urls(),
        "has_ptz": st.capabilities.has_ptz,
        "user": {"username": s["username"], "level": s["level"]},
    }


# ---- generic section get/put (same document ONVIF uses) --------------------------------------

SECTIONS = {"time": "time", "network": "network", "osd": "osd", "io": "io", "motion": "motion", "security": "security"}


@router.get("/config/{section}")
async def get_section(section: str, s=Depends(_session), rt=Depends(_camera)):
    data = rt.state.model_dump(mode="json")
    if section not in data:
        raise HTTPException(404, "Unknown section")
    return data[section]


@router.put("/config/{section}")
async def put_section(section: str, request: Request, s=Depends(need("Administrator")), rt=Depends(_camera)):
    from pydantic import TypeAdapter

    if section not in SECTIONS:
        raise HTTPException(404, "Section not editable")
    try:
        value = TypeAdapter(CameraState.model_fields[section].annotation).validate_python(await request.json())
    except Exception as exc:
        raise HTTPException(422, str(exc)) from None
    await rt.update(lambda st: setattr(st, section, value), {SECTIONS[section]})
    return rt.state.model_dump(mode="json")[section]


@router.get("/streams", response_model=StreamsOut)
async def streams(s=Depends(_session), rt=Depends(_camera)):
    st = rt.state
    return {
        "encoders": [e.model_dump() for e in st.video_encoders],
        "options": {k: v.model_dump() for k, v in st.capabilities.stream_options.items()},
    }


@router.put("/streams/{token}", response_model=VideoEncoderConfig)
async def put_stream(token: str, body: dict, s=Depends(need("Administrator")), rt=Depends(_camera)):
    allowed = set(VideoEncoderConfig.model_fields) - {"token", "stream_key"}
    try:
        await ops.set_video_encoder(rt, token, {k: v for k, v in body.items() if k in allowed})
    except OnvifFault as exc:
        raise _fault(exc) from None
    return rt.state.encoder(token).model_dump()


@router.get("/image", response_model=ImagingSettings)
async def image(s=Depends(_session), rt=Depends(_camera)):
    return rt.state.imaging.model_dump()


@router.put("/image", response_model=ImagingSettings)
async def put_image(body: dict, s=Depends(need("Operator")), rt=Depends(_camera)):
    allowed = set(ImagingSettings.model_fields)
    await ops.set_imaging(rt, {k: v for k, v in body.items() if k in allowed})
    return rt.state.imaging.model_dump()


@router.post("/osd")
async def add_osd(body: dict, s=Depends(need("Administrator")), rt=Depends(_camera)):
    try:
        item = await ops.upsert_osd(rt, OsdItem(**{**body, "token": "NEW"}), create=True)
    except (OnvifFault, ValueError) as exc:
        raise HTTPException(422, str(getattr(exc, "reason", exc))) from None
    return item.model_dump()


@router.delete("/osd/{token}")
async def del_osd(token: str, s=Depends(need("Administrator")), rt=Depends(_camera)):
    try:
        await ops.delete_osd(rt, token)
    except OnvifFault as exc:
        raise _fault(exc) from None
    return {"ok": True}


@router.post("/io/relay/{token}")
async def relay(token: str, active: bool, s=Depends(need("Operator")), rt=Depends(_camera)):
    try:
        rt.set_relay(token, active, origin=f"web:{s['username']}")
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None
    return {"ok": True}


# ---- PTZ ---------------------------------------------------------------------------------------

class PtzMoveIn(BaseModel):
    pan: float = 0
    tilt: float = 0
    zoom: float = 0
    timeout_s: float = 5


@router.post("/ptz/move")
async def ptz_move(body: PtzMoveIn, s=Depends(need("Operator")), rt=Depends(_camera)):
    if not rt.state.capabilities.has_ptz:
        raise HTTPException(404, "No PTZ")
    rt.ptz.continuous(body.pan, body.tilt, body.zoom, body.timeout_s)
    return {"ok": True}


@router.post("/ptz/stop")
async def ptz_stop(s=Depends(need("Operator")), rt=Depends(_camera)):
    rt.ptz.stop()
    return {"ok": True}


@router.get("/ptz/status", response_model=PtzStatusOut)
async def ptz_status(s=Depends(_session), rt=Depends(_camera)):
    p = rt.ptz
    return {"pan": p.pan, "tilt": p.tilt, "zoom": p.zoom, "moving": p.pt_moving or p.zoom_moving, "presets": [x.model_dump() for x in rt.state.ptz.presets]}


@router.post("/ptz/presets")
async def ptz_set_preset(name: str | None = None, token: str | None = None, s=Depends(need("Operator")), rt=Depends(_camera)):
    try:
        return {"token": await ops.set_preset(rt, name, token)}
    except OnvifFault as exc:
        raise _fault(exc) from None


@router.post("/ptz/presets/{token}/goto")
async def ptz_goto(token: str, s=Depends(need("Operator")), rt=Depends(_camera)):
    pr = next((p for p in rt.state.ptz.presets if p.token == token), None)
    if pr is None:
        raise HTTPException(404, "Preset not found")
    rt.ptz.absolute(pr.pan, pr.tilt, pr.zoom)
    return {"ok": True}


@router.delete("/ptz/presets/{token}")
async def ptz_remove(token: str, s=Depends(need("Operator")), rt=Depends(_camera)):
    try:
        await ops.remove_preset(rt, token)
    except OnvifFault as exc:
        raise _fault(exc) from None
    return {"ok": True}


# ---- users -------------------------------------------------------------------------------------

class UserIn(BaseModel):
    username: str
    password: str
    level: Literal["Administrator", "Operator", "User"] = "User"


@router.get("/users", response_model=list[CamUser])
async def users(s=Depends(need("Administrator")), rt=Depends(_camera)):
    return [{"username": u.username, "level": u.level} for u in rt.users.values()]


@router.post("/users")
async def add_user(body: UserIn, s=Depends(need("Administrator")), rt=Depends(_camera)):
    try:
        await user_ops.create_user(rt, body.username, body.password, body.level)
    except OnvifFault as exc:
        raise _fault(exc) from None
    return {"ok": True}


@router.put("/users/{username}")
async def update_user(username: str, body: dict, s=Depends(need("Administrator")), rt=Depends(_camera)):
    try:
        await user_ops.update_user(rt, username, body.get("password"), body.get("level"))
    except OnvifFault as exc:
        raise _fault(exc) from None
    return {"ok": True}


@router.delete("/users/{username}")
async def delete_user(username: str, s=Depends(need("Administrator")), rt=Depends(_camera)):
    try:
        await user_ops.delete_user(rt, username)
    except OnvifFault as exc:
        raise _fault(exc) from None
    return {"ok": True}


# ---- maintenance -------------------------------------------------------------------------------

@router.post("/system/reboot")
async def reboot(s=Depends(need("Administrator")), rt=Depends(_camera)):
    rt.log(f"reboot from web by {s['username']}")
    rt.request_reboot()
    return {"ok": True}


@router.post("/system/factory-reset")
async def factory_reset(hard: bool = False, s=Depends(need("Administrator")), rt=Depends(_camera)):
    await cam_services.factory_default(rt, hard)
    rt.request_reboot()
    return {"ok": True}


@router.post("/system/firmware")
async def firmware(file: UploadFile, s=Depends(need("Administrator")), rt=Depends(_camera)):
    """Fake upgrade: accept the file, bump the build number, reboot. Nothing is flashed."""
    size = 0
    while chunk := await file.read(1 << 20):
        size += len(chunk)
    old = rt.state.identity.firmware_version
    build = int("".join(ch for ch in old.split("build")[-1] if ch.isdigit()) or 0) + 1
    new = f"{old.split(' build')[0]} build {build}"
    await rt.update(lambda st: setattr(st.identity, "firmware_version", new), {"identity"})
    rt.log(f"firmware upgrade {file.filename} ({size} bytes): {old} -> {new}")
    rt.request_reboot(delay=2)
    return {"ok": True, "old_version": old, "new_version": new, "bytes": size}


@router.get("/system/config/export", response_model=CameraState)
async def export_config(s=Depends(need("Administrator")), rt=Depends(_camera)):
    return rt.state.model_dump(mode="json")


@router.post("/system/config/import")
async def import_config(body: dict, s=Depends(need("Administrator")), rt=Depends(_camera)):
    try:
        imported = CameraState.model_validate(body)
    except Exception as exc:
        raise HTTPException(422, f"Invalid config: {exc}") from None
    imported.identity = rt.state.identity  # identity is per device, never imported
    await rt.update(lambda st: cam_services._replace(st, imported), {"source", "stream", "encoders", "imaging", "osd", "time", "network", "ptz", "io", "profiles", "scopes"})
    return {"ok": True}


@router.get("/system/log", response_model=LogLines)
async def system_log(s=Depends(need("Operator")), rt=Depends(_camera)):
    return {"lines": list(rt.logs)}


@router.post("/live/{stream}/whep")
async def whep(stream: str, request: Request, s=Depends(_session), rt=Depends(_camera)):
    return await whep_offer(rt, stream, request, f"/api/cam/v1/live/{stream}/whep")


@router.delete("/live/{stream}/whep/{session}")
async def whep_delete(stream: str, session: str, rt=Depends(_camera)):
    return await whep_close(rt, stream, session)
