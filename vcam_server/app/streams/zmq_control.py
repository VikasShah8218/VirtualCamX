"""Live filter commands to a running FFmpeg through its `zmq` filter.

pyzmq's asyncio integration does not work on the Windows Proactor loop, so we use a plain
blocking REQ socket in a worker thread. A REQ socket is unusable after a timeout, so it is
re-created on any error.
"""
import asyncio
import logging
import threading

import zmq

logger = logging.getLogger("vcam.stream")
_ctx = zmq.Context.instance()


class ZmqControl:
    def __init__(self, port: int):
        self.port = port
        self._sock: zmq.Socket | None = None
        self._lock = threading.Lock()

    def _socket(self) -> zmq.Socket:
        if self._sock is None:
            s = _ctx.socket(zmq.REQ)
            s.setsockopt(zmq.RCVTIMEO, 1000)
            s.setsockopt(zmq.SNDTIMEO, 1000)
            s.setsockopt(zmq.LINGER, 0)
            s.connect(f"tcp://127.0.0.1:{self.port}")
            self._sock = s
        return self._sock

    def _send_blocking(self, commands: list[str]) -> bool:
        with self._lock:
            for cmd in commands:
                try:
                    s = self._socket()
                    s.send_string(cmd)
                    reply = s.recv_string()
                    if not reply.startswith("0"):
                        logger.debug("zmq %s -> %s", cmd, reply)
                except zmq.ZMQError as exc:
                    logger.debug("zmq command %r failed: %s", cmd, exc)
                    self._reset()
                    return False
        return True

    def _reset(self) -> None:
        if self._sock is not None:
            self._sock.close(0)
            self._sock = None

    async def send(self, commands: list[str]) -> bool:
        if not commands:
            return True
        return await asyncio.to_thread(self._send_blocking, commands)

    def close(self) -> None:
        with self._lock:
            self._reset()
