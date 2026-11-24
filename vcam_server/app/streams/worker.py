"""StreamWorker: owns the FFmpeg process of one camera.

Reconcile, not command: after any state change the worker builds the desired StreamSpec and
compares it with the running one. Only live params changed -> ZMQ command. Anything else
changed -> restart FFmpeg (the NVR sees an RTSP reconnect, same as a real camera).
"""
import asyncio
import logging
import time
from collections import deque
from enum import Enum
from typing import TYPE_CHECKING

from app.streams.ffmpeg_builder import LiveParams, StreamSpec, build_argv
from app.streams.spec import build_spec, live_params
from app.streams.zmq_control import ZmqControl
from settings.settings import settings
from utilities import procutil

if TYPE_CHECKING:
    from app.runtime.camera_runtime import CameraRuntime

logger = logging.getLogger("vcam.stream")

BACKOFF = [1, 2, 5, 10, 30]
DEBOUNCE_S = 0.3
SPEC_RECHECK_S = 5.0


class WorkerStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    BACKOFF = "backoff"
    ERROR = "error"


class StreamWorker:
    def __init__(self, rt: "CameraRuntime"):
        self.rt = rt
        self.status = WorkerStatus.STOPPED
        self.proc: asyncio.subprocess.Process | None = None
        self.spec: StreamSpec | None = None
        self.stderr_tail: deque[str] = deque(maxlen=50)
        self.restarts = 0
        self.started_at: float | None = None
        self.last_error: str | None = None
        self._task: asyncio.Task | None = None
        self._restart_evt = asyncio.Event()
        self._enabled = False
        self._zmq: ZmqControl | None = None
        self._live_sent: LiveParams | None = None
        self._live_pending = False
        self._live_task: asyncio.Task | None = None
        self._debounce_task: asyncio.Task | None = None

    # ---- lifecycle ---------------------------------------------------------------------------
    def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        self._task = asyncio.ensure_future(self._supervise())

    async def stop(self) -> None:
        self._enabled = False
        self._restart_evt.set()
        for t in (self._debounce_task, self._live_task):
            if t:
                t.cancel()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None
        await self._kill()
        self.status = WorkerStatus.STOPPED

    def restart(self) -> None:
        self._restart_evt.set()

    # ---- reconcile ---------------------------------------------------------------------------
    def reconcile(self) -> None:
        """Called after any state change. Debounced so a burst of changes = one restart."""
        if not self._enabled:
            return
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.ensure_future(self._reconcile_later())

    async def _reconcile_later(self) -> None:
        await asyncio.sleep(DEBOUNCE_S)
        try:
            desired = build_spec(self.rt)
        except Exception:
            logger.exception("[%s] could not build stream spec", self.rt.name)
            return
        if self.spec is None or desired.restart_key() != self.spec.restart_key():
            logger.info("[%s] stream settings changed -> restarting FFmpeg", self.rt.name)
            self._restart_evt.set()
        else:
            self.push_live()

    def push_live(self) -> None:
        """Send current live params (imaging / PTZ crop) over ZMQ, throttled to ~10/s."""
        self._live_pending = True
        if self._live_task is None or self._live_task.done():
            self._live_task = asyncio.ensure_future(self._live_loop())

    async def _live_loop(self) -> None:
        while self._live_pending:
            self._live_pending = False
            if self._zmq is None or self.status != WorkerStatus.RUNNING:
                return
            want = live_params(self.rt)
            have = self._live_sent or LiveParams()
            cmds = []
            if (want.brightness, want.contrast, want.saturation) != (have.brightness, have.contrast, have.saturation):
                cmds += [
                    f"eq@img brightness {want.brightness}",
                    f"eq@img contrast {want.contrast}",
                    f"eq@img saturation {want.saturation}",
                ]
            if want.gray != have.gray:
                cmds.append(f"hue@ir s {0 if want.gray else 1}")
            if want.crop != have.crop and want.crop[0]:
                w, h, x, y = want.crop
                cmds += [f"crop@ptz w {w}", f"crop@ptz h {h}", f"crop@ptz x {x}", f"crop@ptz y {y}"]
            if cmds and await self._zmq.send(cmds):
                self._live_sent = want
            await asyncio.sleep(0.1)

    # ---- supervisor --------------------------------------------------------------------------
    async def _supervise(self) -> None:
        failures = 0
        while self._enabled:
            self._restart_evt.clear()
            try:
                self.spec = build_spec(self.rt)
                argv = build_argv(
                    self.spec, settings.ffmpeg_path, self.rt.manager.mediamtx.publish_base(),
                    settings.x264_preset, freeze_file=self.rt.faults.freeze_file,
                )
            except Exception as exc:
                logger.exception("[%s] cannot build FFmpeg command", self.rt.name)
                self.last_error = str(exc)
                self.status = WorkerStatus.ERROR
                await self._wait_restart(10)
                continue

            self.status = WorkerStatus.STARTING
            self.stderr_tail.clear()
            started = time.monotonic()
            try:
                self.proc = await procutil.start_process(argv, cwd=str(settings.data_dir))
            except OSError as exc:
                self.last_error = f"cannot start ffmpeg: {exc}"
                self.status = WorkerStatus.ERROR
                logger.error("[%s] %s", self.rt.name, self.last_error)
                await self._wait_restart(10)
                continue
            self.started_at = time.time()
            self.status = WorkerStatus.RUNNING
            self._live_sent = self.spec.live
            self._zmq = ZmqControl(self.spec.zmq_port) if self.spec.zmq_port else None
            stderr_task = asyncio.ensure_future(self._read_stderr(self.proc))
            logger.info("[%s] FFmpeg started (pid %s, %s, %s)", self.rt.name, self.proc.pid, self.spec.mode, self.spec.input.kind)

            exited = await self._run_until_exit_or_restart()
            await self._kill()
            stderr_task.cancel()
            if self._zmq:
                self._zmq.close()
                self._zmq = None
            if not self._enabled:
                break
            if exited:  # unexpected exit
                ran_for = time.monotonic() - started
                failures = failures + 1 if ran_for < 15 else 1
                self.restarts += 1
                self.last_error = " | ".join(list(self.stderr_tail)[-3:]) or "ffmpeg exited"
                delay = BACKOFF[min(failures - 1, len(BACKOFF) - 1)]
                self.status = WorkerStatus.ERROR if failures >= 5 else WorkerStatus.BACKOFF
                logger.warning("[%s] FFmpeg exited (rc=%s); retry in %ss: %s", self.rt.name,
                               self.proc.returncode if self.proc else "?", delay, self.last_error[-300:])
                self.rt.log(f"stream worker exited, retry in {delay}s")
                await self._wait_restart(delay)
            else:
                failures = 0
                self.restarts += 1

        self.status = WorkerStatus.STOPPED

    async def _run_until_exit_or_restart(self) -> bool:
        """True = FFmpeg exited by itself; False = restart requested."""
        assert self.proc
        wait_exit = asyncio.ensure_future(self.proc.wait())
        try:
            while True:
                wait_restart = asyncio.ensure_future(self._restart_evt.wait())
                done, _ = await asyncio.wait({wait_exit, wait_restart}, timeout=SPEC_RECHECK_S, return_when=asyncio.FIRST_COMPLETED)
                wait_restart.cancel()
                if wait_exit in done:
                    return True
                if self._restart_evt.is_set():
                    return False
                # Periodic re-check: source file appeared/disappeared, cache variant became ready...
                try:
                    if build_spec(self.rt).restart_key() != self.spec.restart_key():  # type: ignore[union-attr]
                        logger.info("[%s] stream inputs changed -> restarting FFmpeg", self.rt.name)
                        return False
                except Exception:
                    pass
        finally:
            if not wait_exit.done():
                wait_exit.cancel()

    async def _wait_restart(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._restart_evt.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def _kill(self) -> None:
        if self.proc and self.proc.returncode is None:
            await procutil.stop_process(self.proc, b"q", timeout=3)
        self.proc = None

    async def _read_stderr(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stderr
        while True:
            line = await proc.stderr.readline()
            if not line:
                return
            txt = line.decode("utf-8", "replace").rstrip()
            if txt:
                self.stderr_tail.append(txt)

    def info(self) -> dict:
        return {
            "status": self.status.value,
            "pid": self.proc.pid if self.proc else None,
            "mode": self.spec.mode if self.spec else None,
            "input": self.spec.input.kind if self.spec else None,
            "started_at": self.started_at,
            "restarts": self.restarts,
            "last_error": self.last_error,
            "stderr_tail": list(self.stderr_tail)[-10:],
        }
