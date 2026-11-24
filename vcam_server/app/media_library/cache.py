"""Passthrough cache: pre-encode a footage file once per stream profile, then stream with -c copy.

Cache files live at data/cache/<hash(path+fingerprint)>/<profile_key>.mp4. A variant is "ready"
when that file exists, so no index has to be kept in sync. When the original file already
matches a profile (codec, size, fps), the original file is used directly.
"""
import asyncio
import hashlib
import logging
import os
from collections.abc import Callable

from app.media_library import services
from app.streams.ffmpeg_builder import OutputSpec, _encoder_args
from app.system import hub
from settings.settings import settings
from utilities.procutil import run_capture

logger = logging.getLogger("vcam.cache")

_queue: asyncio.Queue | None = None
_jobs: dict[tuple[str, str], dict] = {}  # (path, profile_key) -> {status, error, ...}
_workers: list[asyncio.Task] = []
on_variant_ready: Callable[[str], None] | None = None  # set by CameraManager


def profile_key(o: OutputSpec) -> str:
    return f"{o.encoding}_{o.width}x{o.height}_{o.fps}_{o.bitrate_kbps}k_{o.rc_mode}_g{o.gov}_{o.profile}_q{o.quality:g}"


def _cache_dir(path: str) -> str:
    h = hashlib.sha1(f"{path}|{services.fingerprint(path)}".encode()).hexdigest()[:16]
    return os.path.join(settings.data_dir, "cache", h)


def _original_matches(path: str, o: OutputSpec) -> bool:
    p = services.cached_probe(path)
    if not p:
        return False
    v = p["video"]
    codec = {"H264": "h264", "H265": "hevc", "JPEG": "mjpeg"}[o.encoding]
    return v["codec"] == codec and v["width"] == o.width and v["height"] == o.height and abs((v["fps"] or 0) - o.fps) <= 1


def ready_variant(path: str, o: OutputSpec) -> str | None:
    try:
        if _original_matches(path, o):
            return path
        f = os.path.join(_cache_dir(path), profile_key(o) + ".mp4")
    except OSError:
        return None
    return f if os.path.isfile(f) else None


def request_variants(path: str, outputs: list[OutputSpec]) -> None:
    if _queue is None:
        return
    for o in outputs:
        key = (path, profile_key(o))
        job = _jobs.get(key)
        if job and job["status"] in ("queued", "running", "failed"):
            continue
        _jobs[key] = {"path": path, "profile_key": key[1], "status": "queued", "error": None, "progress": 0}
        _queue.put_nowait((path, o))
        hub.publish("media.job", _jobs[key])


def jobs() -> list[dict]:
    return list(_jobs.values())


def retry_failed(path: str | None = None) -> int:
    n = 0
    for key, job in list(_jobs.items()):
        if job["status"] == "failed" and (path is None or job["path"] == path):
            del _jobs[key]
            n += 1
    if n and on_variant_ready:
        on_variant_ready(path or "")
    return n


async def _run_job(path: str, o: OutputSpec) -> None:
    key = (path, profile_key(o))
    job = _jobs[key]
    job["status"] = "running"
    hub.publish("media.job", job)
    try:
        await services.probe(path)  # also fills the probe cache for _original_matches
        if ready_variant(path, o):
            job["status"] = "ready"
            return
        out_dir = _cache_dir(path)
        os.makedirs(out_dir, exist_ok=True)
        final = os.path.join(out_dir, profile_key(o) + ".mp4")
        tmp = final + ".part.mp4"
        argv = [
            settings.ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-i", path, "-an",
            "-vf", f"scale={o.width}:{o.height}:force_original_aspect_ratio=decrease,pad={o.width}:{o.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={o.fps}"
            + (",format=yuvj420p" if o.encoding == "JPEG" else ",format=yuv420p"),
            *_encoder_args(o, "medium" if o.encoding == "H264" else "fast"),
            "-movflags", "+faststart", tmp,
        ]
        rc, _, err = await run_capture(argv, timeout=6 * 3600)
        if rc != 0:
            raise RuntimeError(err.strip()[-400:] or f"ffmpeg rc={rc}")
        os.replace(tmp, final)
        job["status"] = "ready"
        logger.info("cache variant ready: %s [%s]", path, profile_key(o))
        if on_variant_ready:
            on_variant_ready(path)
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        logger.error("cache job failed for %s [%s]: %s", path, key[1], exc)
    finally:
        hub.publish("media.job", job)


async def _worker() -> None:
    assert _queue is not None
    while True:
        path, o = await _queue.get()
        try:
            await _run_job(path, o)
        finally:
            _queue.task_done()


def start_workers() -> None:
    global _queue
    _queue = asyncio.Queue()
    for _ in range(max(1, settings.cache_job_workers)):
        _workers.append(asyncio.ensure_future(_worker()))


def stop_workers() -> None:
    for t in _workers:
        t.cancel()
    _workers.clear()
