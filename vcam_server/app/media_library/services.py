"""Footage by path: ffprobe checks and a server-side file browser.

A path always means a path on the machine running VirtualCamX. Files are used in place.
"""
import json
import os
import string
import sys
from pathlib import Path

from settings.settings import settings
from utilities.procutil import run_capture

VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".ts", ".m4v", ".flv", ".webm", ".mpg", ".mpeg", ".h264", ".h265", ".hevc", ".mts", ".wmv"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp"}

_probe_cache: dict[tuple[str, str], dict] = {}


class ProbeError(Exception):
    pass


def fingerprint(path: str) -> str:
    st = os.stat(path)
    return f"{st.st_size}-{int(st.st_mtime)}"


def _fps(rate: str | None) -> float:
    try:
        num, den = (rate or "0/1").split("/")
        return round(float(num) / float(den), 3) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


async def probe(path: str) -> dict:
    """ffprobe a file. Raises ProbeError with a user-readable reason."""
    if not path:
        raise ProbeError("Path is empty")
    if not os.path.exists(path):
        raise ProbeError(f"File not found: {path}")
    if os.path.isdir(path):
        raise ProbeError("Path is a folder, not a file")
    if not os.access(path, os.R_OK):
        raise ProbeError("File is not readable (permissions)")
    fp = fingerprint(path)
    cached = _probe_cache.get((path, fp))
    if cached:
        return cached
    rc, out, err = await run_capture(
        [settings.ffprobe_path, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], timeout=30
    )
    if rc != 0:
        raise ProbeError(f"Not a readable media file: {err.strip()[:300] or 'ffprobe failed'}")
    data = json.loads(out or "{}")
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if v is None:
        raise ProbeError("File has no video track")
    fmt = data.get("format", {})
    result = {
        "path": path,
        "fingerprint": fp,
        "format": fmt.get("format_name"),
        "duration_s": float(fmt.get("duration") or 0) or None,
        "size_bytes": int(fmt.get("size") or 0),
        "bitrate_kbps": int(int(fmt.get("bit_rate") or 0) / 1000) or None,
        "video": {
            "codec": v.get("codec_name"),
            "profile": v.get("profile"),
            "width": v.get("width"),
            "height": v.get("height"),
            "fps": _fps(v.get("avg_frame_rate")) or _fps(v.get("r_frame_rate")),
            "pix_fmt": v.get("pix_fmt"),
        },
        "audio": {"codec": a.get("codec_name"), "sample_rate": a.get("sample_rate"), "channels": a.get("channels")} if a else None,
    }
    _probe_cache[(path, fp)] = result
    return result


def cached_probe(path: str) -> dict | None:
    try:
        return _probe_cache.get((path, fingerprint(path)))
    except OSError:
        return None


def roots() -> list[dict]:
    if sys.platform == "win32":
        out = []
        for letter in string.ascii_uppercase:
            d = f"{letter}:\\"
            if os.path.exists(d):
                out.append({"name": d, "path": d, "is_dir": True})
        return out
    return [{"name": "/", "path": "/", "is_dir": True}, {"name": str(Path.home()), "path": str(Path.home()), "is_dir": True}]


def browse(path: str, show_all: bool = False) -> dict:
    p = Path(path)
    if not p.exists():
        raise ProbeError(f"Folder not found: {path}")
    if not p.is_dir():
        raise ProbeError("Not a folder")
    entries = []
    try:
        items = list(os.scandir(p))
    except PermissionError as exc:
        raise ProbeError("Access denied") from exc
    for e in items:
        try:
            is_dir = e.is_dir()
        except OSError:
            continue
        if e.name.startswith(("$", ".")):
            continue
        ext = os.path.splitext(e.name)[1].lower()
        kind = "dir" if is_dir else "video" if ext in VIDEO_EXT else "image" if ext in IMAGE_EXT else "other"
        if kind == "other" and not show_all:
            continue
        size = None
        if not is_dir:
            try:
                size = e.stat().st_size
            except OSError:
                pass
        entries.append({"name": e.name, "path": e.path, "kind": kind, "is_dir": is_dir, "size_bytes": size})
    entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    parent = str(p.parent) if p.parent != p else None
    return {"path": str(p), "parent": parent, "entries": entries}
