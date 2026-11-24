from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, status

from app.auth.deps import AdminDep
from app.auth.services import decode_token
from app.system import hub, services
from app.system.responses import HealthOut, NicOut, StatsOut
from settings.settings import settings
from utilities.netutil import list_nics

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/health", response_model=HealthOut)
async def health():
    """Public: lets scripts and the UI check that the server is up."""
    return services.health()


@router.get("/stats", dependencies=[AdminDep], response_model=StatsOut)
async def stats():
    return services.STATS


@router.get("/nics", dependencies=[AdminDep], response_model=list[NicOut])
async def nics():
    return list_nics()


@router.get("/settings", dependencies=[AdminDep])
async def get_settings():
    s = settings.model_dump(mode="json")
    s.pop("secret_key", None)
    s.pop("admin_default_password", None)
    s.pop("cam_default_password", None)
    return s


@router.put("/settings", dependencies=[AdminDep])
async def put_settings(changes: dict[str, Any]):
    """Change runtime-safe settings (see services.EDITABLE_SETTINGS). Persisted in the database."""
    try:
        await services.update_settings(changes)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return await get_settings()


@router.get("/settings/editable", dependencies=[AdminDep])
async def editable_settings() -> list[str]:
    return list(services.EDITABLE_SETTINGS)


ws_router = APIRouter()


@ws_router.websocket("/api/v1/ws")
async def ws(websocket: WebSocket, token: str | None = None):
    if settings.manager_auth_enabled and not (token and decode_token(token)):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await hub.serve(websocket)
