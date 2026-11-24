from fastapi import Depends, HTTPException, Query, Request, status

from app.auth.services import decode_token
from settings.settings import settings


async def require_admin(request: Request, token: str | None = Query(default=None, include_in_schema=False)) -> str:
    """Bearer token in the Authorization header (or ?token= for WebSocket / <img> URLs)."""
    if not settings.manager_auth_enabled:
        return "anonymous"
    header = request.headers.get("authorization", "")
    raw = header[7:] if header.lower().startswith("bearer ") else token
    user = decode_token(raw) if raw else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return user


AdminDep = Depends(require_admin)
