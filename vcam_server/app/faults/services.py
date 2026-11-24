"""Apply / clear faults and run their timers (expiry, flapping, repeated stream drops)."""
import logging
import os
import shutil
from datetime import timedelta

from app.faults.models import FaultRecord
from app.faults.state import FAULT_TYPES, ActiveFault
from app.system import hub
from settings.settings import settings
from utilities.common import utcnow

logger = logging.getLogger("vcam.faults")

ONE_SHOT = {"reboot"}


class FaultError(Exception):
    pass


async def apply_fault(rt, kind: str, params: dict | None = None, duration_s: float | None = None) -> dict:
    if kind not in FAULT_TYPES:
        raise FaultError(f"Unknown fault type {kind}")
    params = {**FAULT_TYPES[kind]["params"], **(params or {})}

    if kind == "reboot":
        rt.request_reboot(float(params.get("seconds", settings.reboot_seconds)), delay=0)
        rt.log(f"fault: reboot ({params.get('seconds')}s)")
        hub.publish("fault", {"camera_id": rt.camera_id, "type": kind, "action": "applied"})
        return {"type": kind, "params": params, "one_shot": True}

    if kind == "stream_drop" and not float(params.get("repeat_every_s") or 0):
        n = await rt.manager.mediamtx.kick_readers(rt.path_prefix)
        rt.log(f"fault: stream drop ({n} RTSP clients kicked)")
        hub.publish("fault", {"camera_id": rt.camera_id, "type": kind, "action": "applied", "kicked": n})
        return {"type": kind, "params": params, "one_shot": True, "kicked": n}

    if rt.faults.has(kind):
        await clear_fault(rt, kind)
    now = utcnow()
    expires = now + timedelta(seconds=duration_s) if duration_s else None
    rec = await FaultRecord.create(camera_id=rt.camera_id, type=kind, params=params, started_at=now, expires_at=expires)
    fault = ActiveFault(rec.id, kind, params, now, expires)
    rt.faults.active[kind] = fault
    await _activate(rt, fault)
    rt.log(f"fault applied: {kind} {params}{f' for {duration_s:g}s' if duration_s else ''}")
    hub.publish("fault", {"camera_id": rt.camera_id, "type": kind, "action": "applied"})
    return fault.to_json()


async def _activate(rt, f: ActiveFault, restoring: bool = False) -> None:
    kind = f.type
    if kind == "offline":
        if not restoring:
            await rt.go_offline()
    elif kind == "flapping":
        f.runtime["next_toggle"] = utcnow() + timedelta(seconds=float(f.params.get("online_s", 30)))
        f.runtime["offline"] = False
    elif kind == "stream_drop":
        f.runtime["next_drop"] = utcnow()
    elif kind == "freeze":
        rt.faults.freeze_file = _freeze_frame(rt)
        rt.worker.reconcile()
    elif kind == "black":
        rt.worker.reconcile()
        if not restoring:
            rt.trigger("video_loss", True, origin="fault")
    elif kind == "clock_drift":
        rt.clock.fault_offset = float(f.params.get("offset_s", 600))
        rt.write_osd_files(force=True)
    elif kind == "password_changed":
        await rt.manager.sync_rtsp_users()


def _freeze_frame(rt) -> str | None:
    src = settings.data_dir / "snapshots" / f"{rt.path_prefix}.jpg"
    if not src.exists():
        src = settings.data_dir / "snapshots" / f"{rt.path_prefix}_grab.jpg"
    if not src.exists():
        return None
    dst = settings.data_dir / "snapshots" / f"{rt.path_prefix}_freeze.jpg"
    shutil.copyfile(src, dst)
    return os.path.relpath(dst, settings.data_dir)


async def clear_fault(rt, kind: str) -> bool:
    f = rt.faults.active.pop(kind, None)
    if f is None:
        return False
    await FaultRecord.filter(id=f.id).update(active=False)
    if kind in ("offline", "flapping"):
        await rt.go_online()
    elif kind == "freeze":
        rt.faults.freeze_file = None
        rt.worker.reconcile()
    elif kind == "black":
        rt.worker.reconcile()
        rt.trigger("video_loss", False, origin="fault")
    elif kind == "clock_drift":
        rt.clock.fault_offset = 0.0
        rt.write_osd_files(force=True)
    elif kind == "password_changed":
        await rt.manager.sync_rtsp_users()
    rt.log(f"fault cleared: {kind}")
    hub.publish("fault", {"camera_id": rt.camera_id, "type": kind, "action": "cleared"})
    return True


async def clear_all(rt) -> int:
    n = 0
    for kind in list(rt.faults.active):
        n += await clear_fault(rt, kind)
    return n


async def restore_faults(rt) -> None:
    """At server start: re-apply faults that were active (and not expired) before the restart."""
    now = utcnow()
    for rec in await FaultRecord.filter(camera_id=rt.camera_id, active=True):
        if rec.expires_at and rec.expires_at <= now:
            await FaultRecord.filter(id=rec.id).update(active=False)
            continue
        f = ActiveFault(rec.id, rec.type, rec.params or {}, rec.started_at, rec.expires_at)
        rt.faults.active[rec.type] = f
        await _activate(rt, f, restoring=True)


async def fault_tick() -> None:
    """Every second: expire faults, run flapping and repeated stream drops."""
    from app.runtime.manager import manager

    now = utcnow()
    for rt in manager.all():
        for kind, f in list(rt.faults.active.items()):
            if f.expires_at and f.expires_at <= now:
                await clear_fault(rt, kind)
                continue
            if kind == "flapping" and f.runtime.get("next_toggle") and now >= f.runtime["next_toggle"]:
                if f.runtime.get("offline"):
                    await rt.go_online()
                    f.runtime["offline"] = False
                    f.runtime["next_toggle"] = now + timedelta(seconds=float(f.params.get("online_s", 30)))
                else:
                    await rt.go_offline()
                    f.runtime["offline"] = True
                    f.runtime["next_toggle"] = now + timedelta(seconds=float(f.params.get("offline_s", 10)))
            if kind == "stream_drop" and now >= f.runtime.get("next_drop", now):
                try:
                    await rt.manager.mediamtx.kick_readers(rt.path_prefix)
                except Exception:
                    pass
                f.runtime["next_drop"] = now + timedelta(seconds=float(f.params.get("repeat_every_s") or 30))
