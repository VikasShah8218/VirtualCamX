"""The ASGI app served on every camera listener (ONVIF, snapshot, camera web page + API).

One app object is shared by all listeners; CameraBoundApp puts the camera id in the scope.
"""
from fastapi import FastAPI, HTTPException, Request, Response

from app.onvif import dispatcher
from app.onvif.endpoint import handle_onvif
from app.onvif.security import digest_challenge, verify_http_auth


def current_camera(request: Request):
    from app.runtime.manager import manager

    rt = manager.get(request.scope.get("vcam_camera_id", -1))
    if rt is None:
        raise HTTPException(503, "camera not available")
    return rt


def build_camera_app() -> FastAPI:
    dispatcher.load_handlers()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def server_header(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["Server"] = "VirtualCamX-Webs"
        return resp

    @app.post("/onvif/{rest:path}")
    async def onvif(request: Request, rest: str):
        return await handle_onvif(request, current_camera(request))

    @app.get("/onvif/{rest:path}")
    async def onvif_get(rest: str):
        return Response("ONVIF endpoint: use SOAP over HTTP POST", status_code=405, headers={"Allow": "POST"})

    @app.get("/snapshot/{token}.jpg")
    async def snapshot(request: Request, token: str):
        rt = current_camera(request)
        if rt.state.security.snapshot_auth:
            res = verify_http_auth(request.headers.get("authorization"), "GET", rt.users, True)
            if not res.ok or rt.faults.auth_broken():
                return Response("Unauthorized", status_code=401, headers={"WWW-Authenticate": digest_challenge()})
        from app.streams.snapshot import get_snapshot

        data = await get_snapshot(rt, token)
        if data is None:
            return Response("snapshot not available yet", status_code=503)
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    from app.camera_api.router import router as cam_router

    app.include_router(cam_router)

    from app.system.static import spa_file

    # Registered last: the Camera Web Page (client-side routing), like a real camera's web UI
    @app.get("/{full_path:path}", include_in_schema=False)
    async def web_page(request: Request, full_path: str):
        current_camera(request)
        if full_path.startswith(("api/", "onvif/", "snapshot/")):
            raise HTTPException(404, "Not found")
        return spa_file(full_path, "camera.html")

    return app
