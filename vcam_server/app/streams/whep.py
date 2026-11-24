"""WebRTC (WHEP) signaling proxy to MediaMTX, shared by the Manager API and the camera web API.

The browser never gets MediaMTX credentials: it POSTs its SDP offer here and we forward it
with the internal user. MediaMTX answers with a session URL (Location); we rewrite it to our
own path so the browser can DELETE (close) the session through us. The session id is a
random UUID, so the DELETE needs no login.
"""
import httpx
from fastapi import HTTPException, Request, Response

from settings.settings import settings

_FORWARD = ("content-type", "etag", "accept-patch", "link")


def _mtx_base(rt, stream: str) -> str:
    return f"http://127.0.0.1:{settings.mediamtx_webrtc_port}/{rt.path_prefix}/{stream}/whep"


async def whep_offer(rt, stream: str, request: Request, public_base: str) -> Response:
    """public_base: this endpoint's own path, e.g. /api/v1/cameras/3/live/main/whep"""
    if stream not in {e.stream_key for e in rt.state.video_encoders}:
        raise HTTPException(404, "Unknown stream")
    mtx = rt.manager.mediamtx
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            _mtx_base(rt, stream),
            content=await request.body(),
            headers={"Content-Type": request.headers.get("content-type", "application/sdp")},
            auth=(mtx.publisher_user, mtx.publisher_pass),
        )
    headers = {k: v for k, v in r.headers.items() if k.lower() in _FORWARD}
    location = r.headers.get("location")
    if location:
        headers["Location"] = f"{public_base}/{location.rstrip('/').rsplit('/', 1)[-1]}"
    return Response(r.content, status_code=r.status_code, headers=headers)


async def whep_close(rt, stream: str, session: str) -> Response:
    if not session.replace("-", "").isalnum():
        raise HTTPException(400, "Bad session id")
    mtx = rt.manager.mediamtx
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.delete(f"{_mtx_base(rt, stream)}/{session}", auth=(mtx.publisher_user, mtx.publisher_pass))
    # Closing a session that MediaMTX already dropped (peer connection closed first) is fine
    return Response(status_code=200 if r.status_code in (200, 404) else r.status_code)
