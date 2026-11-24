from fastapi import APIRouter, HTTPException

from app.auth.deps import AdminDep
from app.inspector import buffer
from app.system.responses import InspectorEntryOut, InspectorListOut
from app.cameras.responses import OkOut

router = APIRouter(prefix="/api/v1/inspector", tags=["inspector"], dependencies=[AdminDep])


@router.get("", response_model=InspectorListOut)
async def query(camera_id: int | None = None, op: str | None = None, client_ip: str | None = None, since_id: int = 0, limit: int = 200):
    return {"items": buffer.query(camera_id, op, client_ip, since_id, min(limit, 2000))}


@router.get("/{entry_id}", response_model=InspectorEntryOut)
async def get_entry(entry_id: int):
    e = buffer.get(entry_id)
    if e is None:
        raise HTTPException(404, "Entry not found (it may have been rotated out)")
    return {**e.summary(), "request_xml": e.request_xml, "response_xml": e.response_xml}


@router.delete("", response_model=OkOut)
async def clear(camera_id: int | None = None):
    buffer.clear(camera_id)
    return {"ok": True}
