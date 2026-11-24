"""ONVIF event subscriptions: PullPoint (tev) and Base Notification push (wsnt)."""
import asyncio
import logging
import secrets
from collections import deque
from datetime import datetime, timedelta

import httpx

from app.events.messages import EventMessage, notification_message_xml
from app.events.topics import topic_matches
from app.onvif import soap
from app.onvif.xml import el

logger = logging.getLogger("vcam.events")

MAX_PULL_TIMEOUT_S = 60.0
_http: httpx.AsyncClient | None = None


def http_client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=5.0)
    return _http


class Subscription:
    kind = "base"

    def __init__(self, filters: list[list[str]] | None, termination: datetime, address: str):
        self.id = secrets.token_hex(8)
        self.filters = filters
        self.termination = termination
        self.address = address  # filled after id known
        self.closed = False

    def matches(self, topic: str) -> bool:
        return topic_matches(self.filters, topic)

    def deliver(self, msg: EventMessage) -> None:
        raise NotImplementedError

    def close(self) -> None:
        self.closed = True


class PullPointSubscription(Subscription):
    kind = "pullpoint"

    def __init__(self, filters, termination, address, initial_ttl: float):
        super().__init__(filters, termination, address)
        self.queue: deque[EventMessage] = deque(maxlen=1000)
        self._event = asyncio.Event()
        self.initial_ttl = initial_ttl

    def deliver(self, msg: EventMessage) -> None:
        self.queue.append(msg)
        self._event.set()

    async def pull(self, timeout: float, limit: int) -> list[EventMessage]:
        timeout = max(0.0, min(timeout, MAX_PULL_TIMEOUT_S))
        if not self.queue and timeout > 0:
            self._event.clear()
            try:
                await asyncio.wait_for(self._event.wait(), timeout)
            except asyncio.TimeoutError:
                pass
        out = []
        while self.queue and len(out) < max(1, limit):
            out.append(self.queue.popleft())
        if not self.queue:
            self._event.clear()
        return out

    def close(self) -> None:
        super().close()
        self._event.set()  # wake a waiting PullMessages


class PushSubscription(Subscription):
    kind = "push"

    def __init__(self, filters, termination, address, consumer_url: str, camera_name: str):
        super().__init__(filters, termination, address)
        self.consumer_url = consumer_url
        self.camera_name = camera_name
        self.queue: asyncio.Queue[EventMessage] = asyncio.Queue(maxsize=1000)
        self.failures = 0
        self.task = asyncio.ensure_future(self._sender())

    def deliver(self, msg: EventMessage) -> None:
        try:
            self.queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass

    async def _sender(self) -> None:
        client = http_client()
        while not self.closed:
            msg = await self.queue.get()
            batch = [msg]
            while not self.queue.empty() and len(batch) < 20:
                batch.append(self.queue.get_nowait())
            header = el("wsa:Action", "http://docs.oasis-open.org/wsn/bw-2/NotificationConsumer/Notify") + el(
                "wsa:To", self.consumer_url
            )
            body = el("wsnt:Notify", [notification_message_xml(m, self.address) for m in batch])
            payload = soap.envelope(body, "1.2", header)
            try:
                r = await client.post(self.consumer_url, content=payload, headers={"Content-Type": soap.content_type("1.2")})
                if r.status_code >= 400:
                    raise httpx.HTTPError(f"HTTP {r.status_code}")
                self.failures = 0
            except Exception as exc:
                self.failures += 1
                logger.warning("[%s] push notify to %s failed (%d): %s", self.camera_name, self.consumer_url, self.failures, exc)
                if self.failures >= 3:
                    logger.warning("[%s] dropping push subscription %s after 3 failures", self.camera_name, self.id)
                    self.closed = True

    def close(self) -> None:
        super().close()
        self.task.cancel()


def termination_from(now: datetime, requested: str | None, default_s: float, parse_duration, parse_dt) -> tuple[datetime, float]:
    """InitialTerminationTime may be a duration (PT60S) or an absolute dateTime."""
    if requested:
        d = parse_duration(requested)
        if d is not None and d > 0:
            return now + timedelta(seconds=d), d
        dt = parse_dt(requested)
        if dt is not None and dt > now:
            return dt, (dt - now).total_seconds()
    return now + timedelta(seconds=default_s), default_s
