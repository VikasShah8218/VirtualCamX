"""JPEG snapshots. Encode mode: FFmpeg writes one per second. Passthrough: grab on demand."""
import asyncio
import os
import time

from settings.settings import settings
from utilities.procutil import run_capture

_sem: asyncio.Semaphore | None = None
_cache: dict[str, tuple[float, bytes]] = {}
CACHE_S = 2.0


def _snapshot_file(rt) -> str:
    return os.path.join(settings.data_dir, "snapshots", f"{rt.path_prefix}.jpg")


async def get_snapshot(rt, profile_token: str | None = None) -> bytes | None:
    spec = rt.worker.spec
    if spec and spec.snapshot_file:
        try:
            with open(_snapshot_file(rt), "rb") as f:
                data = f.read()
            if data:
                return data
        except OSError:
            pass
    return await grab(rt, profile_token)


async def grab(rt, profile_token: str | None = None) -> bytes | None:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(max(1, settings.snapshot_max_parallel))
    key = rt.path_prefix
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_S:
        return hit[1]
    stream = "main"
    prof = rt.state.profile(profile_token) if profile_token else None
    enc = rt.state.encoder(prof.vec_token) if prof and prof.vec_token else None
    if enc:
        stream = enc.stream_key
    url = f"{rt.manager.mediamtx.internal_read_base()}/{rt.path_prefix}/{stream}"
    async with _sem:
        rc, _, _ = await run_capture(
            [settings.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-rtsp_transport", "tcp", "-i", url,
             "-frames:v", "1", "-q:v", "4", "-y", os.path.join(settings.data_dir, "snapshots", f"{key}_grab.jpg")],
            timeout=10,
        )
    if rc != 0:
        return None
    try:
        with open(os.path.join(settings.data_dir, "snapshots", f"{key}_grab.jpg"), "rb") as f:
            data = f.read()
    except OSError:
        return None
    _cache[key] = (time.monotonic(), data)
    return data
