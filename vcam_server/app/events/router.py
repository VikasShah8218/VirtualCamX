from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth.deps import AdminDep
from app.events import simulator
from app.events.models import EventLog, EventSchedule
from app.runtime.camera_runtime import CameraStatus
from app.runtime.manager import manager
from app.system.responses import CountOut, EventOut, EventStateOut, IdOut, ScheduleOut
from app.cameras.responses import OkOut

router = APIRouter(prefix="/api/v1", tags=["events"], dependencies=[AdminDep])

Kind = Literal["motion", "tamper", "digital_input", "video_loss"]


class TriggerIn(BaseModel):
    kind: Kind
    state: bool | None = None  # None = pulse (true now, false after duration_s)
    duration_s: float = 10.0
    token: str | None = None  # digital input token


class BulkTriggerIn(TriggerIn):
    ids: list[int] | None = None  # None = all running cameras


class ScheduleIn(BaseModel):
    camera_id: int
    kind: Kind
    token: str | None = None
    mode: Literal["periodic", "random"] = "periodic"
    interval_s: float = Field(60, ge=1)
    interval_max_s: float = Field(120, ge=1)
    active_s: float = Field(10, ge=0.1)
    enabled: bool = True


def _fire(rt, body: TriggerIn, origin: str) -> None:
    if body.state is None:
        rt.pulse(body.kind, body.duration_s, body.token, origin)
    else:
        rt.trigger(body.kind, body.state, body.token, origin)


@router.post("/cameras/{camera_id}/events/trigger", response_model=OkOut)
async def trigger(camera_id: int, body: TriggerIn):
    rt = manager.get(camera_id)
    if rt is None:
        raise HTTPException(404, "Camera not found")
    if rt.status != CameraStatus.RUNNING:
        raise HTTPException(409, f"Camera is {rt.status.value}")
    try:
        _fire(rt, body, "api")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {"ok": True}


@router.post("/events/bulk-trigger", response_model=CountOut, response_model_exclude_none=True)
async def bulk_trigger(body: BulkTriggerIn):
    targets = [manager.get(i) for i in body.ids] if body.ids else manager.all()
    n = 0
    for rt in targets:
        if rt and rt.status == CameraStatus.RUNNING:
            try:
                _fire(rt, body, "api")
                n += 1
            except ValueError:
                pass
    return {"triggered": n}


@router.get("/cameras/{camera_id}/events", response_model=list[EventOut])
async def camera_events(camera_id: int, limit: int = 100):
    rows = await EventLog.filter(camera_id=camera_id).order_by("-id").limit(min(limit, 1000))
    return [
        {"id": r.id, "topic": r.topic, "operation": r.operation, "source": r.source, "data": r.data, "origin": r.origin, "utc_time": r.utc_time}
        for r in rows
    ]


@router.get("/cameras/{camera_id}/events/state", response_model=list[EventStateOut])
async def camera_event_state(camera_id: int):
    rt = manager.get(camera_id)
    if rt is None:
        raise HTTPException(404, "Camera not found")
    return [m.to_json() for m in rt.broker.properties.values()]


@router.get("/event-schedules", response_model=list[ScheduleOut])
async def list_schedules(camera_id: int | None = None):
    q = EventSchedule.all() if camera_id is None else EventSchedule.filter(camera_id=camera_id)
    return await q.values()


@router.post("/event-schedules", status_code=201, response_model=IdOut)
async def create_schedule(body: ScheduleIn):
    if manager.get(body.camera_id) is None:
        raise HTTPException(404, "Camera not found")
    s = await EventSchedule.create(**body.model_dump())
    await simulator.reload()
    return {"id": s.id}


@router.patch("/event-schedules/{schedule_id}", response_model=OkOut)
async def update_schedule(schedule_id: int, body: ScheduleIn):
    if not await EventSchedule.filter(id=schedule_id).update(**body.model_dump()):
        raise HTTPException(404, "Schedule not found")
    await simulator.reload()
    return {"ok": True}


@router.delete("/event-schedules/{schedule_id}", response_model=OkOut)
async def delete_schedule(schedule_id: int):
    await EventSchedule.filter(id=schedule_id).delete()
    await simulator.reload()
    return {"ok": True}
