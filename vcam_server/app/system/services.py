"""Start-up self-check, farm statistics and host metrics."""
import logging
import time

import psutil

from app.runtime.camera_runtime import CameraStatus
from app.runtime.manager import manager
from app.system import hub
from settings.settings import settings
from utilities.netutil import is_tcp_port_free
from utilities.procutil import run_capture

logger = logging.getLogger("vcam.system")

HEALTH: dict = {}
STATS: dict = {"cameras": {}, "farm": {}}
_last_bytes: dict[str, tuple[float, int, int]] = {}  # path -> (t, bytes_in, bytes_out)
_started = time.time()


async def self_check() -> dict:
    checks: dict = {}
    rc, out, err = await run_capture([settings.ffmpeg_path, "-hide_banner", "-version"], timeout=15)
    checks["ffmpeg"] = {"ok": rc == 0, "path": settings.ffmpeg_path, "version": (out.splitlines() or [""])[0] if rc == 0 else err[:200]}
    if rc == 0:
        _, filters, _ = await run_capture([settings.ffmpeg_path, "-hide_banner", "-filters"], timeout=15)
        _, encoders, _ = await run_capture([settings.ffmpeg_path, "-hide_banner", "-encoders"], timeout=15)
        checks["ffmpeg"]["zmq_filter"] = " zmq " in filters
        checks["ffmpeg"]["drawtext"] = " drawtext " in filters
        checks["ffmpeg"]["libx264"] = "libx264" in encoders
        checks["ffmpeg"]["libx265"] = "libx265" in encoders
        if not checks["ffmpeg"]["zmq_filter"]:
            logger.warning("FFmpeg has no zmq filter: live imaging/PTZ changes will restart the stream")
    rc, out, _ = await run_capture([settings.ffprobe_path, "-hide_banner", "-version"], timeout=15)
    checks["ffprobe"] = {"ok": rc == 0, "path": settings.ffprobe_path}
    checks["mediamtx_binary"] = {"path": settings.mediamtx_path}
    ports = {
        "manager": settings.manager_port,
        "rtsp": settings.mediamtx_rtsp_port,
        "webrtc": settings.mediamtx_webrtc_port,
        "mediamtx_api": settings.mediamtx_api_port,
    }
    checks["ports_free_at_start"] = {k: is_tcp_port_free(p) for k, p in ports.items() if k != "manager"}
    HEALTH.update(checks)
    return checks


def health() -> dict:
    wsd = manager.wsd
    return {
        **HEALTH,
        "mediamtx": {"running": manager.mediamtx.running(), "restarts": manager.mediamtx.restarts, "log_tail": list(manager.mediamtx.log_tail)[-10:]},
        "ws_discovery": {"running": bool(wsd and wsd.transport), "error": wsd.error if wsd else None, "probes_seen": wsd.probes_seen if wsd else 0},
        "host_ip": manager.host_ip,
        "addr_mode": settings.addr_mode,
        "uptime_s": int(time.time() - _started),
    }


async def stats_tick() -> None:
    now = time.monotonic()
    per_cam: dict[int, dict] = {}
    by_prefix = {rt.path_prefix: rt for rt in manager.all()}
    try:
        paths = await manager.mediamtx.list_paths()
    except Exception:
        paths = []
    for p in paths:
        name = p.get("name", "")
        prefix, _, stream = name.partition("/")
        rt = by_prefix.get(prefix)
        if rt is None:
            continue
        b_in, b_out = int(p.get("bytesReceived") or 0), int(p.get("bytesSent") or 0)
        prev = _last_bytes.get(name)
        kbps_in = kbps_out = 0.0
        if prev and now > prev[0]:
            dt = now - prev[0]
            kbps_in = max(0.0, (b_in - prev[1]) * 8 / 1000 / dt)
            kbps_out = max(0.0, (b_out - prev[2]) * 8 / 1000 / dt)
        _last_bytes[name] = (now, b_in, b_out)
        c = per_cam.setdefault(rt.camera_id, {"readers": 0, "kbps_in": 0.0, "kbps_out": 0.0, "streams": {}})
        readers = len(p.get("readers") or [])
        c["readers"] += readers
        c["kbps_in"] += kbps_in
        c["kbps_out"] += kbps_out
        c["streams"][stream] = {"ready": p.get("ready"), "readers": readers, "kbps": round(kbps_in, 1)}
    for c in per_cam.values():
        c["kbps_in"] = round(c["kbps_in"], 1)
        c["kbps_out"] = round(c["kbps_out"], 1)

    runtimes = manager.all()
    farm = {
        "cameras": len(runtimes),
        "running": sum(1 for r in runtimes if r.status == CameraStatus.RUNNING),
        "offline": sum(1 for r in runtimes if r.status in (CameraStatus.OFFLINE, CameraStatus.REBOOTING)),
        "error": sum(1 for r in runtimes if r.status == CameraStatus.ERROR),
        "stopped": sum(1 for r in runtimes if r.status == CameraStatus.STOPPED),
        "rtsp_clients": sum(c["readers"] for c in per_cam.values()),
        "kbps_out": round(sum(c["kbps_out"] for c in per_cam.values()), 1),
        "subscriptions": sum(r.broker.count() for r in runtimes),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": psutil.virtual_memory().percent,
        "active_faults": sum(len(r.faults.active) for r in runtimes),
    }
    STATS["cameras"] = per_cam
    STATS["farm"] = farm
    hub.publish("camera.stats", {"farm": farm, "cameras": per_cam})


# ---- editable runtime settings (B6) -------------------------------------------------------------
# Only settings that are safe to change while running. Ports, paths and addressing need a restart
# and stay in .env.
EDITABLE_SETTINGS = {
    "cam_default_user": str,
    "cam_default_password": str,
    "reboot_seconds": int,
    "wssec_time_tolerance_s": int,
    "max_subscriptions_per_camera": int,
    "x264_preset": str,
}
_OVERRIDES_KEY = "settings_overrides"


async def load_setting_overrides() -> None:
    from app.system.models import SystemSetting

    row = await SystemSetting.get_or_none(key=_OVERRIDES_KEY)
    for k, v in ((row.value if row else None) or {}).items():
        if k in EDITABLE_SETTINGS:
            setattr(settings, k, EDITABLE_SETTINGS[k](v))


async def update_settings(changes: dict) -> dict:
    from app.system.models import SystemSetting

    clean = {}
    for k, v in changes.items():
        if k not in EDITABLE_SETTINGS:
            raise ValueError(f"Setting '{k}' cannot be changed at runtime (edit .env and restart)")
        try:
            clean[k] = EDITABLE_SETTINGS[k](v)
        except (TypeError, ValueError):
            raise ValueError(f"Bad value for {k}") from None
    if "x264_preset" in clean and clean["x264_preset"] not in ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium"):
        raise ValueError("x264_preset must be one of ultrafast, superfast, veryfast, faster, fast, medium")
    row = await SystemSetting.get_or_none(key=_OVERRIDES_KEY)
    merged = {**((row.value if row else None) or {}), **clean}
    await SystemSetting.update_or_create(defaults={"value": merged}, key=_OVERRIDES_KEY)
    for k, v in clean.items():
        setattr(settings, k, v)
    return merged
