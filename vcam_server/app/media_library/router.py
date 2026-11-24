from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth.deps import AdminDep
from app.media_library import cache, services
from app.media_library.models import MediaItem
from app.runtime.manager import manager
from app.system.responses import BrowseOut, CountOut, FsRoot, JobOut, MediaItemOut, ProbeOut
from app.cameras.responses import OkOut

router = APIRouter(prefix="/api/v1", tags=["media"], dependencies=[AdminDep])


class PathIn(BaseModel):
    path: str
    label: str = ""


@router.get("/fs/roots", response_model=list[FsRoot])
async def fs_roots():
    return services.roots()


@router.get("/fs/browse", response_model=BrowseOut)
async def fs_browse(path: str, show_all: bool = False):
    try:
        return services.browse(path, show_all)
    except services.ProbeError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/media/probe", response_model=ProbeOut)
async def probe(body: PathIn):
    try:
        return await services.probe(body.path)
    except services.ProbeError as exc:
        raise HTTPException(422, str(exc)) from None


@router.get("/media", response_model=list[MediaItemOut])
async def list_media():
    items = await MediaItem.all().order_by("-id")
    out = []
    for m in items:
        used_by = [rt.camera_id for rt in manager.all() if rt.state.source.path == m.path]
        out.append({"id": m.id, "path": m.path, "label": m.label, "probe": m.probe, "used_by": used_by})
    return out


@router.post("/media", status_code=201, response_model=MediaItemOut)
async def register_media(body: PathIn):
    try:
        p = await services.probe(body.path)
    except services.ProbeError as exc:
        raise HTTPException(422, str(exc)) from None
    item, _ = await MediaItem.update_or_create(
        defaults={"label": body.label, "probe": p, "fingerprint": p["fingerprint"]}, path=body.path
    )
    return {"id": item.id, "path": item.path, "label": item.label, "probe": item.probe}


@router.delete("/media/{media_id}", response_model=OkOut)
async def delete_media(media_id: int):
    await MediaItem.filter(id=media_id).delete()
    return {"ok": True}


@router.get("/media/jobs", response_model=list[JobOut])
async def cache_jobs():
    return cache.jobs()


@router.post("/media/jobs/retry", response_model=CountOut, response_model_exclude_none=True)
async def retry_jobs(path: str | None = None):
    return {"retried": cache.retry_failed(path)}
