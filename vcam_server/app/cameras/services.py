"""Camera CRUD, bulk create, address allocation, source switching, factory default."""
import logging
import os
import random
import uuid

from app.cameras.models import Camera, CameraUser
from app.cameras.state import CameraState, SourceSpec
from app.media_library import services as media
from app.runtime.manager import manager
from app.templates.builtin import BUILTIN_TEMPLATES, build_state
from app.templates.models import CameraTemplate
from settings.settings import settings
from utilities.crypto import encrypt_secret
from utilities.netutil import ip_range, is_tcp_port_free, random_mac

logger = logging.getLogger("vcam.cameras")


class CameraError(Exception):
    """User-facing error (HTTP 4xx)."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


# ---- templates ---------------------------------------------------------------------------------

async def get_template(key: str) -> dict:
    if key in BUILTIN_TEMPLATES:
        return BUILTIN_TEMPLATES[key]
    t = await CameraTemplate.get_or_none(key=key)
    if t is None:
        raise CameraError(f"Unknown template '{key}'", 404)
    return t.definition


# ---- allocation ---------------------------------------------------------------------------------

async def _used() -> tuple[set[int], set[int], set[str], set[str], set[str]]:
    rows = await Camera.all().values("number", "http_port", "ip", "name", "state")
    numbers = {r["number"] for r in rows}
    ports = {r["http_port"] for r in rows}
    ips = {r["ip"] for r in rows if r["ip"]}
    names = {r["name"] for r in rows}
    macs = {(r["state"] or {}).get("identity", {}).get("mac", "") for r in rows}
    return numbers, ports, ips, names, macs


def _next_free_port(used_ports: set[int], start: int | None = None) -> int:
    lo, hi = settings.port_range
    for p in range(max(lo, start or lo), hi + 1):
        if p in used_ports or p in settings.reserved_ports:
            continue
        if is_tcp_port_free(p):
            return p
    raise CameraError(f"No free port left in range {settings.cam_port_range}", 409)


def _next_free_ip(used_ips: set[str]) -> str:
    for ip in ip_range(settings.cam_ip_range):
        if ip not in used_ips:
            return ip
    raise CameraError(f"No free IP left in range {settings.cam_ip_range}", 409)


async def validate_source(src: SourceSpec) -> None:
    if src.type in ("file", "image"):
        if not src.path:
            raise CameraError("Source path is required")
        try:
            if src.type == "file":
                await media.probe(src.path)
            elif not os.path.isfile(src.path):
                raise media.ProbeError(f"File not found: {src.path}")
        except media.ProbeError as exc:
            raise CameraError(str(exc)) from None
    if src.type == "rtsp" and not (src.url or "").startswith(("rtsp://", "rtsps://")):
        raise CameraError("RTSP relay source needs an rtsp:// URL")


# ---- create ------------------------------------------------------------------------------------

async def create_camera(
    *,
    name: str | None = None,
    template_key: str = "bullet_2mp",
    source: SourceSpec | None = None,
    stream_mode: str = "encode",
    http_port: int | None = None,
    ip: str | None = None,
    username: str | None = None,
    password: str | None = None,
    enabled: bool = True,
    start: bool = True,
    _used_cache: tuple | None = None,
    _validate_source: bool = True,
) -> Camera:
    if isinstance(source, dict):
        source = SourceSpec.model_validate(source)
    template = await get_template(template_key)
    numbers, ports, ips, names, macs = _used_cache or await _used()
    number = max(numbers, default=0) + 1
    name = (name or f"VCam-{number:03d}").strip()
    if name in names:
        raise CameraError(f"Camera name '{name}' already exists", 409)
    addr_mode = settings.addr_mode
    if addr_mode == "port":
        if http_port is not None:
            if http_port in ports or http_port in settings.reserved_ports:
                raise CameraError(f"Port {http_port} is already used", 409)
        else:
            http_port = _next_free_port(ports)
    else:
        if ip and ip in ips:
            raise CameraError(f"IP {ip} is already used", 409)
        ip = ip or _next_free_ip(ips)
        http_port = http_port or 80
    if source is not None and _validate_source:
        await validate_source(source)

    mac = random_mac()
    while mac in macs:
        mac = random_mac()
    serial = f"VCX{number:05d}{random.randint(0, 0xFFFF):04X}"
    state = build_state(template, name=name, serial=serial, mac=mac, endpoint_uuid=str(uuid.uuid4()))
    state.network.hostname = name.replace(" ", "-")
    state.time.tz = host_posix_tz()
    if source is not None:
        state.source = source
    state.stream_mode = stream_mode  # type: ignore[assignment]

    cam = await Camera.create(
        number=number, name=name, enabled=enabled, template_key=template_key, addr_mode=addr_mode, ip=ip,
        http_port=http_port, state=state.model_dump(mode="json"),
    )
    await CameraUser.create(
        camera_id=cam.id,
        username=username or settings.cam_default_user,
        password_enc=encrypt_secret(password or settings.cam_default_password),
        level="Administrator",
    )
    numbers.add(number)
    ports.add(http_port)
    if ip:
        ips.add(ip)
    names.add(name)
    macs.add(mac)
    rt = await manager.add_runtime(cam)
    if enabled and start:
        await rt.start()
    logger.info("camera %s created (%s, port %s)", name, template_key, http_port)
    return cam


def host_posix_tz() -> str:
    """The host's current UTC offset as a POSIX TZ string (POSIX signs are inverted: IST = UTC-5:30)."""
    from datetime import datetime

    offset = datetime.now().astimezone().utcoffset()
    minutes = int(offset.total_seconds() // 60) if offset else 0
    if minutes == 0:
        return "UTC0"
    h, m = divmod(abs(minutes), 60)
    return f"UTC{'-' if minutes > 0 else '+'}{h}" + (f":{m:02d}" if m else "")


def _render_name(pattern: str, n: int) -> str:
    try:
        return pattern.format(n=n)
    except (KeyError, ValueError, IndexError):
        return f"{pattern}-{n:03d}"


async def bulk_create(
    *,
    count: int,
    template_key: str = "bullet_2mp",
    name_pattern: str = "VCam-{n:03d}",
    first_index: int | None = None,
    source: SourceSpec | None = None,
    spread_paths: list[str] | None = None,
    offset_step_s: float = 0.0,
    stream_mode: str = "encode",
    start_port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    start: bool = True,
) -> list[Camera]:
    if not 1 <= count <= 1000:
        raise CameraError("count must be 1..1000")
    if isinstance(source, dict):
        source = SourceSpec.model_validate(source)
    await get_template(template_key)
    if source is not None:
        await validate_source(source)
    for p in spread_paths or []:
        await validate_source(SourceSpec(type="file", path=p))
    cache = await _used()
    numbers, ports, *_ = cache
    n0 = first_index if first_index is not None else max(numbers, default=0) + 1
    created: list[Camera] = []
    next_port = start_port
    for i in range(count):
        src = source
        if spread_paths:
            src = SourceSpec(type="file", path=spread_paths[i % len(spread_paths)])
        if src is not None and offset_step_s:
            src = src.model_copy(update={"start_offset": round(i * offset_step_s, 3)})
        port = None
        if settings.addr_mode == "port" and next_port:
            port = _next_free_port(ports, next_port)
            next_port = port + 1
        cam = await create_camera(
            name=_render_name(name_pattern, n0 + i), template_key=template_key, source=src, stream_mode=stream_mode,
            http_port=port, username=username, password=password, start=False, _used_cache=cache, _validate_source=False,
        )
        created.append(cam)
    if start:
        await manager.start_enabled_ids([c.id for c in created])
    return created


# ---- update / delete ---------------------------------------------------------------------------

async def rename_camera(rt, name: str) -> None:
    name = name.strip()
    if not name:
        raise CameraError("Name cannot be empty")
    if await Camera.filter(name=name).exclude(id=rt.camera_id).exists():
        raise CameraError(f"Camera name '{name}' already exists", 409)
    old = rt.name
    await Camera.filter(id=rt.camera_id).update(name=name)
    rt.name = name

    def mut(st: CameraState):
        st.scopes = [s if not s.startswith("onvif://www.onvif.org/name/") else f"onvif://www.onvif.org/name/{name.replace(' ', '_')}" for s in st.scopes]
        for o in st.osd:
            if o.kind == "Plain" and o.plain_text == old:
                o.plain_text = name

    await rt.update(mut, {"scopes", "osd"})


async def set_enabled(rt, enabled: bool) -> None:
    await Camera.filter(id=rt.camera_id).update(enabled=enabled)
    rt.enabled = enabled
    if enabled:
        await rt.start()
    else:
        await rt.stop()


async def change_port(rt, port: int) -> None:
    if settings.addr_mode != "port":
        raise CameraError("Ports can only be changed in Port Mode")
    if port in settings.reserved_ports or await Camera.filter(http_port=port).exclude(id=rt.camera_id).exists():
        raise CameraError(f"Port {port} is already used", 409)
    lo, hi = settings.port_range
    if not lo <= port <= hi:
        raise CameraError(f"Port must be in range {settings.cam_port_range}")
    await Camera.filter(id=rt.camera_id).update(http_port=port)
    rt.http_port = port
    if rt.enabled:
        await rt.restart()


async def delete_camera(camera_id: int) -> None:
    rt = manager.get(camera_id)
    if rt is None:
        raise CameraError("Camera not found", 404)
    await manager.remove_runtime(camera_id)
    await Camera.filter(id=camera_id).delete()
    from app.events.models import EventSchedule
    from app.faults.models import FaultRecord

    await EventSchedule.filter(camera_id=camera_id).delete()
    await FaultRecord.filter(camera_id=camera_id).delete()
    for f in (f"snapshots/{rt.path_prefix}.jpg",):
        try:
            os.remove(settings.data_dir / f)
        except OSError:
            pass


async def set_source(rt, src: SourceSpec, stream_mode: str | None = None) -> None:
    """Live footage switch: the NVR sees only a short RTSP reconnect."""
    await validate_source(src)

    def mut(st: CameraState):
        st.source = src
        if stream_mode:
            st.stream_mode = stream_mode  # type: ignore[assignment]

    await rt.update(mut, {"source", "stream"})
    rt.log(f"source changed to {src.type}: {src.path or src.url or src.pattern}")


async def factory_default(rt, hard: bool) -> None:
    template = await get_template(rt.template_key)
    old = rt.state
    fresh = build_state(template, name=rt.name, serial=old.identity.serial_number, mac=old.identity.mac,
                        endpoint_uuid=old.identity.endpoint_uuid)
    fresh.identity = old.identity
    fresh.source = old.source  # footage is a VirtualCamX setting, not a camera setting
    fresh.stream_mode = old.stream_mode
    if not hard:
        fresh.network = old.network
    else:
        fresh.network.hostname = rt.name.replace(" ", "-")

    await rt.update(lambda st: _replace(st, fresh), {"source", "stream", "encoders", "imaging", "osd", "time", "network", "ptz", "io", "profiles", "scopes"})
    if hard:
        from app.cameras.users import reset_users

        await reset_users(rt, settings.cam_default_user, settings.cam_default_password)
    rt.log(f"factory default ({'hard' if hard else 'soft'})")


def _replace(st: CameraState, fresh: CameraState) -> None:
    for field in CameraState.model_fields:
        setattr(st, field, getattr(fresh, field))
