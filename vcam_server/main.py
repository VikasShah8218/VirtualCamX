"""vcam_server entry point:  py main.py

Wires logging, the database, the camera engine, routers and background loops.
The real work lives in app/ (see plan/BACKEND_IMPLEMENTATION_PLAN.md).
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise

from database.config import TORTOISE_ORM
from settings.settings import settings
from utilities.common import run_periodic, spawn


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)-14s %(message)s",
        datefmt="%H:%M:%S",
    )
    # One uvicorn server per camera: keep their start/stop chatter out of the log
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("tortoise").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


logger = logging.getLogger("vcam")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.auth.services import ensure_default_admin
    from app.discovery.wsd import WsDiscovery
    from app.events import simulator
    from app.faults.services import fault_tick
    from app.runtime.manager import manager
    from app.system import services as system

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await Tortoise.init(config=TORTOISE_ORM, _enable_global_fallback=True)
    await Tortoise.generate_schemas(safe=True)
    await ensure_default_admin()
    await system.load_setting_overrides()
    await system.self_check()

    if settings.wsd_enabled:
        manager.wsd = WsDiscovery(manager, settings.wsd_interface_ip or manager.host_ip)
        await manager.wsd.start()
    await manager.startup()
    await simulator.reload()

    loops = [
        spawn(run_periodic("stats", 2.0, system.stats_tick), "stats"),
        spawn(run_periodic("osd_clock", 1.0, manager.osd_tick), "osd_clock"),
        spawn(run_periodic("event_scheduler", 0.5, simulator.scheduler_tick), "event_scheduler"),
        spawn(run_periodic("event_log_flush", 2.0, simulator.flush_event_log), "event_log_flush"),
        spawn(run_periodic("event_log_trim", 600.0, simulator.trim_event_log), "event_log_trim"),
        spawn(run_periodic("subscription_cleanup", 5.0, manager.subscription_cleanup_tick), "subscription_cleanup"),
        spawn(run_periodic("fault_tick", 1.0, fault_tick), "fault_tick"),
        spawn(run_periodic("state_flush", 1.0, manager.flush_state), "state_flush"),
        spawn(run_periodic("mediamtx_watchdog", 5.0, manager.mediamtx_watchdog_tick), "mediamtx_watchdog"),
    ]
    logger.info(
        "VirtualCamX ready: Manager http://%s:%s  |  host IP %s  |  %d cameras  |  RTSP :%s",
        settings.manager_host, settings.manager_port, manager.host_ip, len(manager.runtimes), settings.mediamtx_rtsp_port,
    )
    try:
        yield
    finally:
        for t in loops:
            t.cancel()
        if manager.wsd:
            manager.wsd.stop()
        await manager.shutdown()
        await simulator.flush_event_log()
        await Tortoise.close_connections()
        logger.info("VirtualCamX stopped")


def build_app() -> FastAPI:
    from app.auth.router import router as auth_router
    from app.cameras.router import live_router
    from app.cameras.router import router as cameras_router
    from app.events.router import router as events_router
    from app.faults.router import router as faults_router
    from app.inspector.router import router as inspector_router
    from app.media_library.router import router as media_router
    from app.system.router import router as system_router
    from app.system.router import ws_router
    from app.templates.router import router as templates_router

    app = FastAPI(title="VirtualCamX Manager API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    for r in (auth_router, cameras_router, live_router, templates_router, media_router, events_router, faults_router,
              inspector_router, system_router, ws_router):
        app.include_router(r)

    from fastapi import HTTPException

    from app.system.static import spa_file

    # Registered last: everything that is not API/docs is the Manager web app (client-side routing)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def web_app(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        return spa_file(full_path, "index.html")

    return app


app = build_app()


async def run() -> None:
    config = uvicorn.Config(app, host=settings.manager_host, port=settings.manager_port, log_config=None, lifespan="on")
    await uvicorn.Server(config).serve()


if __name__ == "__main__":
    configure_logging()
    if sys.platform == "win32":
        # Proactor (the default) is required for FFmpeg/MediaMTX subprocesses
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run())
