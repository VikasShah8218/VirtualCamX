"""Serving the built web client (vcam_client -> static/web).

One build holds both apps: index.html (Manager UI, served on :9000) and camera.html (Camera Web
Page, served on every camera listener). Unknown paths fall back to the app's HTML so client-side
routes (/cameras/12, /config/video) survive a browser refresh.
"""
from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse, Response

from settings.settings import SERVICE_DIR

WEB_DIR = (SERVICE_DIR / "static" / "web").resolve()

_PLACEHOLDER = """<!doctype html><meta charset="utf-8"><title>VirtualCamX</title>
<body style="font-family:sans-serif;background:#2e3440;color:#eceff4;padding:2rem">
<h2>VirtualCamX</h2><p>The web client is not built yet. Run <code>npm run build</code> in <code>vcam_client/</code>.</p>
<p>API docs: <a style="color:#88c0d0" href="/docs">/docs</a></p></body>"""


def spa_file(path: str, index: str) -> Response:
    if path:
        candidate = (WEB_DIR / path).resolve()
        if candidate.is_file() and WEB_DIR in candidate.parents:
            # Vite puts a content hash in asset names, so they can be cached forever
            cache = "public, max-age=31536000, immutable" if "/assets/" in candidate.as_posix() else "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
    index_file = WEB_DIR / index
    if index_file.is_file():
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})
    return HTMLResponse(_PLACEHOLDER)


def is_built() -> bool:
    return Path(WEB_DIR / "index.html").is_file()
