"""Manager REST API: cameras (CRUD, bulk, control, config sections, users, live)."""
import asyncio

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.auth.deps import AdminDep
from app.cameras import operations as ops
from app.cameras import services, users as user_ops
from app.cameras.schemas import BulkAction, BulkCreate, BulkSourceIn, CameraCreate, CameraPatch, CameraUserIn, CameraUserPatch, SourceIn
from app.cameras.state import CameraState, PtzPreset, SourceSpec
from app.inspector import buffer as inspector
from app.onvif.faults import OnvifFault
from app.runtime.manager import manager
from app.streams.snapshot import get_snapshot
from app.streams.whep import whep_close, whep_offer
from app.cameras.responses import BulkCreatedOut, CameraListOut, CameraOut, CameraUrls, CameraUserOut, ClientsOut, LogOut, OkOut, ResultsOut
from settings.settings import settings

router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"], dependencies=[AdminDep])

# Sections of CameraState editable through PUT /cameras/{id}/state/{section}
EDITABLE_SECTIONS = {
    "identity": "identity",
    "network": "network",
    "time": "time",
    "imaging": "imaging",
    "osd": "osd",
    "io": "io",
    "motion": "motion",
    "security": "security",
    "scopes": "scopes",
    "video_encoders": "encoders",
    "osd_show_events": "osd",
}


def _rt(camera_id: int):
    rt = manager.get(camera_id)
    if rt is None:
        raise HTTPException(404, "Camera not found")
    return rt


def _err(exc: Exception) -> HTTPException:
    if isinstance(exc, services.CameraError):
        return HTTPException(exc.status, str(exc))
    if isinstance(exc, OnvifFault):
        return HTTPException(422, exc.reason)
    if isinstance(exc, ValidationError):
        return HTTPException(422, exc.errors(include_url=False))
    return HTTPException(422, str(exc))


# ---- list / create ----------------------------------------------------------------------------

@router.get("", response_model=CameraListOut)
async def list_cameras(status: str | None = None, q: str | None = None):
    items = [rt.info() for rt in manager.all()]
    if status:
        items = [i for i in items if i["status"] == status]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i["name"].lower() or ql in str(i["http_port"]) or ql in i["ip"]]
    return {"items": items, "total": len(items)}


@router.post("", status_code=201, response_model=CameraOut)
async def create_camera(body: CameraCreate):
    try:
        cam = await services.create_camera(**body.model_dump())
    except (services.CameraError, OnvifFault) as exc:
        raise _err(exc) from None
    return _rt(cam.id).info()


@router.post("/bulk", status_code=201, response_model=BulkCreatedOut)
async def bulk_create(body: BulkCreate):
    try:
        cams = await services.bulk_create(**body.model_dump())
    except (services.CameraError, OnvifFault) as exc:
        raise _err(exc) from None
    return {"created": [_rt(c.id).info() for c in cams]}


@router.post("/bulk-action", response_model=ResultsOut)
async def bulk_action(body: BulkAction):
    results = {}

    async def one(cid: int):
        rt = manager.get(cid)
        if rt is None:
            results[cid] = "not found"
            return
        try:
            if body.action == "start":
                await rt.start()
            elif body.action == "stop":
                await rt.stop()
            elif body.action == "restart":
                await rt.restart()
            elif body.action == "reboot":
                rt.request_reboot(body.params.get("seconds"), delay=0)
            elif body.action == "delete":
                await services.delete_camera(cid)
            elif body.action in ("enable", "disable"):
                await services.set_enabled(rt, body.action == "enable")
            results[cid] = "ok"
        except Exception as exc:
            results[cid] = str(exc)

    sem = asyncio.Semaphore(settings.start_batch_size)

    async def guarded(cid):
        async with sem:
            await one(cid)

    await asyncio.gather(*(guarded(c) for c in body.ids))
    return {"results": results}


@router.put("/bulk-source", response_model=ResultsOut)
async def bulk_source(body: BulkSourceIn):
    results = {}
    for i, cid in enumerate(body.ids):
        rt = manager.get(cid)
        if rt is None:
            results[cid] = "not found"
            continue
        src = body.source
        if body.spread_paths:
            src = SourceSpec(type="file", path=body.spread_paths[i % len(body.spread_paths)])
        if src is None:
            raise HTTPException(422, "source or spread_paths is required")
        if body.offset_step_s:
            src = src.model_copy(update={"start_offset": round(i * body.offset_step_s, 3)})
        try:
            await services.set_source(rt, src, body.stream_mode)
            results[cid] = "ok"
        except Exception as exc:
            results[cid] = str(exc)
    return {"results": results}


# ---- one camera -------------------------------------------------------------------------------

@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(camera_id: int):
    return _rt(camera_id).info()


@router.patch("/{camera_id}", response_model=CameraOut)
async def patch_camera(camera_id: int, body: CameraPatch):
    rt = _rt(camera_id)
    try:
        if body.name is not None and body.name != rt.name:
            await services.rename_camera(rt, body.name)
        if body.http_port is not None and body.http_port != rt.http_port:
            await services.change_port(rt, body.http_port)
        if body.enabled is not None and body.enabled != rt.enabled:
            await services.set_enabled(rt, body.enabled)
    except Exception as exc:
        raise _err(exc) from None
    return rt.info()


@router.delete("/{camera_id}", response_model=OkOut)
async def delete_camera(camera_id: int):
    try:
        await services.delete_camera(camera_id)
    except services.CameraError as exc:
        raise _err(exc) from None
    return {"ok": True}


@router.get("/{camera_id}/urls", response_model=CameraUrls)
async def urls(camera_id: int):
    return _rt(camera_id).urls()


@router.get("/{camera_id}/state", response_model=CameraState)
async def get_state(camera_id: int):
    return _rt(camera_id).state.model_dump(mode="json")


@router.get("/{camera_id}/state/{section}")
async def get_state_section(camera_id: int, section: str):
    st = _rt(camera_id).state.model_dump(mode="json")
    if section not in st:
        raise HTTPException(404, "Unknown section")
    return st[section]


@router.put("/{camera_id}/state/{section}")
async def put_state_section(camera_id: int, section: str, request: Request):
    rt = _rt(camera_id)
    if section not in EDITABLE_SECTIONS:
        raise HTTPException(404, f"Section {section} is not editable here")
    payload = await request.json()
    try:
        value = TypeAdapter(CameraState.model_fields[section].annotation).validate_python(payload)
        if section == "video_encoders":
            for enc in value:
                ops.validate_encoder(rt.state, enc.token, enc.model_dump(exclude={"token", "stream_key"}))
        await rt.update(lambda st: setattr(st, section, value), {EDITABLE_SECTIONS[section]})
    except Exception as exc:
        raise _err(exc) from None
    return rt.state.model_dump(mode="json")[section]


@router.put("/{camera_id}/source", response_model=CameraOut)
async def put_source(camera_id: int, body: SourceIn):
    rt = _rt(camera_id)
    try:
        await services.set_source(rt, body.source, body.stream_mode)
    except Exception as exc:
        raise _err(exc) from None
    return rt.info()


@router.get("/{camera_id}/clients", response_model=ClientsOut)
async def clients(camera_id: int):
    rt = _rt(camera_id)
    sessions = []
    try:
        for s in await manager.mediamtx.list_rtsp_sessions():
            if str(s.get("path", "")).startswith(rt.path_prefix + "/") and s.get("state") == "read":
                sessions.append({k: s.get(k) for k in ("id", "created", "remoteAddr", "path", "transport", "bytesSent")})
    except Exception:
        pass
    return {"rtsp": sessions, "onvif": inspector.clients(camera_id), "subscriptions": rt.broker.summary()}


@router.get("/{camera_id}/log", response_model=LogOut)
async def log(camera_id: int):
    return {"lines": list(_rt(camera_id).logs)}


@router.get("/{camera_id}/snapshot")
async def snapshot(camera_id: int, profile: str | None = None):
    data = await get_snapshot(_rt(camera_id), profile)
    if data is None:
        raise HTTPException(503, "Snapshot not available yet")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ---- camera users -----------------------------------------------------------------------------

@router.get("/{camera_id}/users", response_model=list[CameraUserOut])
async def list_users(camera_id: int):
    return [{"username": u.username, "level": u.level} for u in _rt(camera_id).users.values()]


@router.post("/{camera_id}/users", status_code=201, response_model=OkOut)
async def add_user(camera_id: int, body: CameraUserIn):
    try:
        await user_ops.create_user(_rt(camera_id), body.username, body.password, body.level)
    except OnvifFault as exc:
        raise _err(exc) from None
    return {"ok": True}


@router.patch("/{camera_id}/users/{username}", response_model=OkOut)
async def update_user(camera_id: int, username: str, body: CameraUserPatch):
    try:
        await user_ops.update_user(_rt(camera_id), username, body.password, body.level)
    except OnvifFault as exc:
        raise _err(exc) from None
    return {"ok": True}


@router.delete("/{camera_id}/users/{username}", response_model=OkOut)
async def delete_user(camera_id: int, username: str):
    try:
        await user_ops.delete_user(_rt(camera_id), username)
    except OnvifFault as exc:
        raise _err(exc) from None
    return {"ok": True}


# ---- live view (WebRTC WHEP proxy to MediaMTX) --------------------------------------------------

@router.post("/{camera_id}/live/{stream}/whep")
async def whep(camera_id: int, stream: str, request: Request):
    return await whep_offer(_rt(camera_id), stream, request, f"/api/v1/cameras/{camera_id}/live/{stream}/whep")


# WHEP session close: no login (the session id is an unguessable UUID; the browser's
# fetch(DELETE) on page leave cannot always attach the token)
live_router = APIRouter(prefix="/api/v1/cameras", tags=["cameras"])


@live_router.delete("/{camera_id}/live/{stream}/whep/{session}", status_code=200)
async def whep_delete(camera_id: int, stream: str, session: str):
    return await whep_close(_rt(camera_id), stream, session)


# ---- PTZ (same virtual PTZ the NVR drives over ONVIF) -------------------------------------------

class PtzMove(BaseModel):
    pan: float = 0
    tilt: float = 0
    zoom: float = 0
    timeout_s: float = 2


class PtzStatus(BaseModel):
    pan: float
    tilt: float
    zoom: float
    moving: bool
    presets: list[PtzPreset]


def _ptz_rt(camera_id: int):
    rt = _rt(camera_id)
    if not rt.state.capabilities.has_ptz:
        raise HTTPException(404, "This camera has no PTZ")
    return rt


@router.post("/{camera_id}/ptz/move", response_model=OkOut)
async def ptz_move(camera_id: int, body: PtzMove):
    _ptz_rt(camera_id).ptz.continuous(body.pan, body.tilt, body.zoom, body.timeout_s)
    return {"ok": True}


@router.post("/{camera_id}/ptz/stop", response_model=OkOut)
async def ptz_stop(camera_id: int):
    _ptz_rt(camera_id).ptz.stop()
    return {"ok": True}


@router.get("/{camera_id}/ptz/status", response_model=PtzStatus)
async def ptz_status(camera_id: int):
    rt = _ptz_rt(camera_id)
    p = rt.ptz
    return {"pan": p.pan, "tilt": p.tilt, "zoom": p.zoom, "moving": p.pt_moving or p.zoom_moving, "presets": rt.state.ptz.presets}


@router.post("/{camera_id}/ptz/presets/{preset_token}/goto", response_model=OkOut)
async def ptz_goto(camera_id: int, preset_token: str):
    rt = _ptz_rt(camera_id)
    pr = next((x for x in rt.state.ptz.presets if x.token == preset_token), None)
    if pr is None:
        raise HTTPException(404, "Preset not found")
    rt.ptz.absolute(pr.pan, pr.tilt, pr.zoom)
    return {"ok": True}


@router.post("/{camera_id}/ptz/home", response_model=OkOut)
async def ptz_home(camera_id: int):
    rt = _ptz_rt(camera_id)
    h = rt.state.ptz
    rt.ptz.absolute(h.home_pan, h.home_tilt, h.home_zoom)
    return {"ok": True}


# Explicit routes (a catch-all "/{camera_id}/{action}" would shadow /cameras/{id}/faults in other routers)
async def _control(camera_id: int, action: str, seconds: float | None = None):
    rt = _rt(camera_id)
    if action == "start":
        await rt.start()
    elif action == "stop":
        await rt.stop()
    elif action == "restart":
        await rt.restart()
    elif action == "reboot":
        rt.request_reboot(seconds, delay=0)
    elif action == "factory-reset":
        await services.factory_default(rt, hard=False)
        rt.request_reboot(delay=0)
    return rt.info()


for _action in ("start", "stop", "restart", "reboot", "factory-reset"):
    def _make(action=_action):
        async def endpoint(camera_id: int, seconds: float | None = None):
            return await _control(camera_id, action, seconds)

        endpoint.__name__ = f"camera_{action.replace('-', '_')}"
        router.add_api_route(f"/{{camera_id}}/{action}", endpoint, methods=["POST"], name=endpoint.__name__, response_model=CameraOut)

    _make()
