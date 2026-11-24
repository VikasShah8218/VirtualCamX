"""CameraManager: owns every CameraRuntime, MediaMTX and the WS-Discovery responder."""
import asyncio
import logging
import os
import shutil

from app.cameras.models import Camera, CameraUser
from app.media_library import cache
from app.onvif.security import UserEntry
from app.runtime.camera_runtime import CameraRuntime, CameraStatus
from app.streams.mediamtx import MediaMtx
from settings.settings import settings
from utilities.crypto import decrypt_secret
from utilities.netutil import detect_host_ip

logger = logging.getLogger("vcam.manager")

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


class CameraManager:
    def __init__(self):
        self.runtimes: dict[int, CameraRuntime] = {}
        self.mediamtx = MediaMtx(self._rtsp_users)
        self.host_ip = settings.host_ip or detect_host_ip()
        self.font_rel: str | None = None
        self.camera_app = None  # set in startup (built lazily to avoid import cycles)
        self.wsd = None  # WsDiscovery, set by main
        self._dirty: set[int] = set()

    # ---- startup / shutdown -------------------------------------------------------------------
    async def startup(self) -> None:
        from app.camera_api.app import build_camera_app

        self.camera_app = build_camera_app()
        for sub in ("osd", "snapshots", "fonts", "cache", "logs"):
            os.makedirs(settings.data_dir / sub, exist_ok=True)
        self._prepare_font()
        cache.on_variant_ready = self._on_variant_ready
        cache.start_workers()
        await self.mediamtx.start()
        await self.load_all()
        await self.start_enabled()

    def _prepare_font(self) -> None:
        dst = settings.data_dir / "fonts" / "osd.ttf"
        if not dst.exists():
            src = next((f for f in FONT_CANDIDATES if os.path.isfile(f)), None)
            if src:
                shutil.copyfile(src, dst)
        self.font_rel = "fonts/osd.ttf" if dst.exists() else None
        if not self.font_rel:
            logger.warning("no TTF font found for OSD; FFmpeg will use fontconfig defaults")

    async def load_all(self) -> None:
        for record in await Camera.all().order_by("number"):
            await self.add_runtime(record)
        logger.info("loaded %d cameras", len(self.runtimes))

    async def add_runtime(self, record: Camera) -> CameraRuntime:
        users = [
            UserEntry(u.username, decrypt_secret(u.password_enc), u.level)
            for u in await CameraUser.filter(camera_id=record.id)
        ]
        rt = CameraRuntime(self, record, users)
        from app.faults.services import restore_faults

        await restore_faults(rt)
        self.runtimes[record.id] = rt
        return rt

    async def start_enabled_ids(self, ids: list[int]) -> None:
        await self.start_enabled([self.runtimes[i] for i in ids if i in self.runtimes])

    async def start_enabled(self, runtimes: list[CameraRuntime] | None = None) -> None:
        enabled = [rt for rt in (runtimes if runtimes is not None else self.all()) if rt.enabled]
        batch = max(1, settings.start_batch_size)
        for i in range(0, len(enabled), batch):
            await asyncio.gather(*(rt.start() for rt in enabled[i : i + batch]))
        if enabled:
            running = sum(1 for rt in enabled if rt.status == CameraStatus.RUNNING)
            logger.info("started %d/%d enabled cameras", running, len(enabled))

    async def shutdown(self) -> None:
        await asyncio.gather(*(rt.stop() for rt in self.runtimes.values()), return_exceptions=True)
        await self.flush_state()
        cache.stop_workers()
        await self.mediamtx.stop()

    # ---- lookup ----------------------------------------------------------------------------------
    def get(self, camera_id: int) -> CameraRuntime | None:
        return self.runtimes.get(camera_id)

    def all(self) -> list[CameraRuntime]:
        return sorted(self.runtimes.values(), key=lambda r: r.number)

    async def remove_runtime(self, camera_id: int) -> None:
        rt = self.runtimes.pop(camera_id, None)
        if rt:
            await rt.stop()
            await self.sync_rtsp_users()

    # ---- users -> MediaMTX -----------------------------------------------------------------------
    def _rtsp_users(self) -> list[dict]:
        out = []
        for rt in self.runtimes.values():
            if rt.faults.auth_broken():
                continue
            for u in rt.users.values():
                out.append({"user": u.username, "pass": u.password, "paths": [rt.path_prefix]})
        return out

    async def sync_rtsp_users(self) -> None:
        try:
            await self.mediamtx.sync_users()
        except Exception:
            logger.exception("MediaMTX user sync failed")

    async def reload_users(self, camera_id: int) -> None:
        rt = self.get(camera_id)
        if not rt:
            return
        rt.users = {
            u.username: UserEntry(u.username, decrypt_secret(u.password_enc), u.level)
            for u in await CameraUser.filter(camera_id=camera_id)
        }
        await self.sync_rtsp_users()

    # ---- persistence -----------------------------------------------------------------------------
    def mark_dirty(self, camera_id: int) -> None:
        self._dirty.add(camera_id)

    async def flush_state(self) -> None:
        dirty, self._dirty = self._dirty, set()
        for cid in dirty:
            rt = self.get(cid)
            if rt:
                await Camera.filter(id=cid).update(state=rt.state.model_dump(mode="json"))

    # ---- discovery hooks -------------------------------------------------------------------------
    def wsd_hello(self, rt: CameraRuntime) -> None:
        if self.wsd:
            self.wsd.hello(rt)

    def wsd_bye(self, rt: CameraRuntime) -> None:
        if self.wsd:
            self.wsd.bye(rt)

    # ---- passthrough cache -------------------------------------------------------------------------
    def _on_variant_ready(self, path: str) -> None:
        for rt in self.runtimes.values():
            if rt.state.source.path == path or not path:
                rt.worker.reconcile()

    # ---- periodic --------------------------------------------------------------------------------
    async def osd_tick(self) -> None:
        for rt in self.runtimes.values():
            if rt.status == CameraStatus.RUNNING:
                rt.write_osd_files()

    async def subscription_cleanup_tick(self) -> None:
        for rt in self.runtimes.values():
            rt.broker.cleanup()

    async def mediamtx_watchdog_tick(self) -> None:
        if await self.mediamtx.watchdog():
            for rt in self.runtimes.values():
                rt.worker.restart()


manager = CameraManager()  # the process-wide singleton
