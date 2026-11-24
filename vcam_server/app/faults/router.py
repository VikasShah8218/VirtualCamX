from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth.deps import AdminDep
from app.faults import services
from app.faults.state import FAULT_TYPES
from app.runtime.manager import manager
from app.system.responses import CountOut, FaultTypeOut
from app.cameras.responses import FaultOut, ResultsOut

router = APIRouter(prefix="/api/v1", tags=["faults"], dependencies=[AdminDep])


class FaultIn(BaseModel):
    type: str
    params: dict = Field(default_factory=dict)
    duration_s: float | None = None


class BulkFaultIn(FaultIn):
    ids: list[int]


def _rt(camera_id: int):
    rt = manager.get(camera_id)
    if rt is None:
        raise HTTPException(404, "Camera not found")
    return rt


@router.get("/faults/types", response_model=dict[str, FaultTypeOut])
async def fault_types():
    return FAULT_TYPES


@router.get("/cameras/{camera_id}/faults", response_model=list[FaultOut])
async def list_faults(camera_id: int):
    return _rt(camera_id).faults.list()


@router.post("/cameras/{camera_id}/faults")
async def apply_fault(camera_id: int, body: FaultIn):
    try:
        return await services.apply_fault(_rt(camera_id), body.type, body.params, body.duration_s)
    except services.FaultError as exc:
        raise HTTPException(422, str(exc)) from None


@router.delete("/cameras/{camera_id}/faults/{fault_type}", response_model=CountOut, response_model_exclude_none=True)
async def clear_fault(camera_id: int, fault_type: str):
    rt = _rt(camera_id)
    if fault_type == "all":
        return {"cleared": await services.clear_all(rt)}
    if not await services.clear_fault(rt, fault_type):
        raise HTTPException(404, "Fault not active")
    return {"cleared": 1}


@router.post("/faults/bulk", response_model=ResultsOut)
async def bulk_fault(body: BulkFaultIn):
    results = {}
    for cid in body.ids:
        rt = manager.get(cid)
        if rt is None:
            results[cid] = "not found"
            continue
        try:
            await services.apply_fault(rt, body.type, body.params, body.duration_s)
            results[cid] = "ok"
        except Exception as exc:
            results[cid] = str(exc)
    return {"results": results}


@router.post("/faults/bulk-clear", response_model=CountOut, response_model_exclude_none=True)
async def bulk_clear(ids: list[int]):
    n = 0
    for cid in ids:
        rt = manager.get(cid)
        if rt:
            n += await services.clear_all(rt)
    return {"cleared": n}
