"""Scheduled / random event generators. One loop fires all due schedules (no task per schedule)."""
import logging
import random
import time

from app.events.broker import EVENT_LOG_BUFFER
from app.events.models import EventLog, EventSchedule

logger = logging.getLogger("vcam.events")

KINDS = ("motion", "tamper", "digital_input", "video_loss")
_schedules: dict[int, EventSchedule] = {}
_next_fire: dict[int, float] = {}


def _interval(s: EventSchedule) -> float:
    if s.mode == "random":
        lo, hi = sorted((max(1.0, s.interval_s), max(1.0, s.interval_max_s)))
        return random.uniform(lo, hi)
    return max(1.0, s.interval_s)


async def reload() -> None:
    _schedules.clear()
    for s in await EventSchedule.filter(enabled=True):
        _schedules[s.id] = s
        _next_fire.setdefault(s.id, time.monotonic() + _interval(s))
    for sid in list(_next_fire):
        if sid not in _schedules:
            _next_fire.pop(sid)


async def scheduler_tick() -> None:
    from app.runtime.camera_runtime import CameraStatus
    from app.runtime.manager import manager

    now = time.monotonic()
    for sid, s in list(_schedules.items()):
        if now < _next_fire.get(sid, now):
            continue
        _next_fire[sid] = now + _interval(s) + max(0.0, s.active_s)
        rt = manager.get(s.camera_id)
        if rt is None or rt.status != CameraStatus.RUNNING:
            continue
        try:
            rt.pulse(s.kind, s.active_s, s.token, origin="schedule")
        except Exception as exc:
            logger.warning("schedule %s failed: %s", sid, exc)


async def flush_event_log() -> None:
    if not EVENT_LOG_BUFFER:
        return
    batch = EVENT_LOG_BUFFER[:500]
    del EVENT_LOG_BUFFER[: len(batch)]
    await EventLog.bulk_create([EventLog(**row) for row in batch])


async def trim_event_log(keep: int = 100_000) -> None:
    total = await EventLog.all().count()
    if total > keep:
        cutoff = await EventLog.all().order_by("-id").offset(keep).first()
        if cutoff:
            await EventLog.filter(id__lte=cutoff.id).delete()
