import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

logger = logging.getLogger("vcam")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


async def run_periodic(name: str, interval: float, func: Callable[[], Awaitable[None]]) -> None:
    """Run `func` every `interval` seconds forever. A failure is logged and never stops the loop."""
    while True:
        try:
            await func()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("periodic task %s failed", name)
        await asyncio.sleep(interval)


def spawn(coro: Awaitable, name: str) -> asyncio.Task:
    """Create a background task whose exception is logged instead of being lost."""
    task = asyncio.ensure_future(coro)
    task.set_name(name)

    def _done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            logger.error("task %s crashed: %r", name, exc, exc_info=exc)

    task.add_done_callback(_done)
    return task


def iso_z(dt: datetime) -> str:
    """xs:dateTime in UTC with a Z suffix (what ONVIF clients expect)."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_duration(text: str) -> float | None:
    """Parse an xs:duration such as PT60S, PT1M30S, PT10.5S, P1D. Returns seconds."""
    import re

    m = re.fullmatch(
        r"\s*-?P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?\s*", text or ""
    )
    if not m or text.strip() in ("P", "PT"):
        return None
    y, mo, d, h, mi, s = m.groups()
    return (
        int(y or 0) * 365 * 86400
        + int(mo or 0) * 30 * 86400
        + int(d or 0) * 86400
        + int(h or 0) * 3600
        + int(mi or 0) * 60
        + float(s or 0)
    )


def parse_xs_datetime(text: str) -> datetime | None:
    try:
        t = text.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None
