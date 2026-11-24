"""CameraListener: one uvicorn Server per camera, all inside the main event loop.

Closing the listener really closes the port, so "offline" and "reboot" look real to an NVR.
"""
import asyncio
import contextlib
import logging

import uvicorn

from utilities.netutil import make_listen_socket

logger = logging.getLogger("vcam.listener")


class _QuietServer(uvicorn.Server):
    """The main (Manager) server owns process signals; camera servers must not touch them."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield


class CameraBoundApp:
    """Puts the camera id into the ASGI scope so routes know which camera they serve."""

    def __init__(self, camera_id: int, app):
        self.camera_id = camera_id
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = dict(scope)
            scope["vcam_camera_id"] = self.camera_id
        await self.app(scope, receive, send)


class CameraListener:
    def __init__(self, camera_id: int, host: str, port: int, app):
        self.camera_id = camera_id
        self.host = host
        self.port = port
        self.app = app
        self.server: _QuietServer | None = None
        self.task: asyncio.Task | None = None

    async def start(self) -> None:
        sock = make_listen_socket(self.host, self.port)  # raises OSError if the port is taken
        config = uvicorn.Config(
            CameraBoundApp(self.camera_id, self.app),
            log_config=None,
            access_log=False,
            lifespan="off",
            timeout_graceful_shutdown=2,
            timeout_keep_alive=30,
            server_header=False,
            proxy_headers=False,
            ws="none",
        )
        self.server = _QuietServer(config)
        self.task = asyncio.ensure_future(self.server.serve(sockets=[sock]))
        for _ in range(200):
            if self.server.started or self.task.done():
                break
            await asyncio.sleep(0.01)
        if self.task.done() and self.task.exception():
            raise OSError(f"listener failed: {self.task.exception()}")

    async def stop(self) -> None:
        if not self.server or not self.task:
            return
        self.server.should_exit = True
        try:
            await asyncio.wait_for(asyncio.shield(self.task), timeout=4)
        except asyncio.TimeoutError:
            self.server.force_exit = True
            try:
                await asyncio.wait_for(self.task, timeout=2)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self.task.cancel()
        except Exception:
            logger.exception("camera %s listener stop failed", self.camera_id)
        self.server = None
        self.task = None
