"""WebSocket hub: pushes live updates (status, stats, events, inspector) to Manager UI clients."""
import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger("vcam.hub")

_clients: dict[WebSocket, asyncio.Queue] = {}


def publish(topic: str, data: dict) -> None:
    """Non-blocking: drop the message for a client whose queue is full (slow browser)."""
    if not _clients:
        return
    msg = json.dumps({"topic": topic, "data": data}, default=str)
    for q in list(_clients.values()):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


async def serve(ws: WebSocket) -> None:
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _clients[ws] = q
    sender = asyncio.ensure_future(_send_loop(ws, q))
    try:
        while True:
            await ws.receive_text()  # we ignore client messages; this detects disconnects
    except Exception:
        pass
    finally:
        sender.cancel()
        _clients.pop(ws, None)


async def _send_loop(ws: WebSocket, q: asyncio.Queue) -> None:
    try:
        while True:
            await ws.send_text(await q.get())
    except Exception:
        pass
