"""Virtual PTZ: a real position that moves over time at the requested speed.

Position uses ONVIF generic spaces: pan/tilt -1..1, zoom 0..1. In Encode mode the
position is turned into a crop window on the source (ePTZ), see crop_rect().
"""
import asyncio
from collections.abc import Callable

TICK = 0.05  # 20 Hz
PAN_TILT_UNITS_PER_S = 0.6  # at speed 1.0
ZOOM_UNITS_PER_S = 0.35


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class PtzController:
    def __init__(self, on_move: Callable[[], None]):
        self.pan = 0.0
        self.tilt = 0.0
        self.zoom = 0.0
        self.pt_moving = False
        self.zoom_moving = False
        self._on_move = on_move
        self._task: asyncio.Task | None = None
        self._velocity = (0.0, 0.0, 0.0)
        self._target: tuple[float, float, float] | None = None
        self._target_speed = (1.0, 1.0)
        self._deadline: float | None = None

    # ---- commands ------------------------------------------------------------------------
    def continuous(self, vx: float, vy: float, vz: float, timeout_s: float | None) -> None:
        self._target = None
        self._velocity = (_clamp(vx, -1, 1), _clamp(vy, -1, 1), _clamp(vz, -1, 1))
        loop = asyncio.get_running_loop()
        self._deadline = loop.time() + timeout_s if timeout_s else None
        self._ensure_task()

    def absolute(self, pan: float | None, tilt: float | None, zoom: float | None, pt_speed: float = 1.0, z_speed: float = 1.0) -> None:
        self._velocity = (0.0, 0.0, 0.0)
        self._deadline = None
        self._target = (
            _clamp(self.pan if pan is None else pan, -1, 1),
            _clamp(self.tilt if tilt is None else tilt, -1, 1),
            _clamp(self.zoom if zoom is None else zoom, 0, 1),
        )
        self._target_speed = (max(0.05, pt_speed or 1.0), max(0.05, z_speed or 1.0))
        self._ensure_task()

    def relative(self, dp: float, dt: float, dz: float, pt_speed: float = 1.0, z_speed: float = 1.0) -> None:
        base = self._target or (self.pan, self.tilt, self.zoom)
        self.absolute(base[0] + dp, base[1] + dt, base[2] + dz, pt_speed, z_speed)

    def stop(self, pan_tilt: bool = True, zoom: bool = True) -> None:
        vx, vy, vz = self._velocity
        if pan_tilt:
            vx = vy = 0.0
        if zoom:
            vz = 0.0
        self._velocity = (vx, vy, vz)
        if self._target and pan_tilt and zoom:
            self._target = None
        if self._velocity == (0.0, 0.0, 0.0) and self._target is None:
            self.pt_moving = self.zoom_moving = False

    def set_position(self, pan: float, tilt: float, zoom: float) -> None:
        self.pan, self.tilt, self.zoom = pan, tilt, zoom
        self._on_move()

    def shutdown(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        self.pt_moving = self.zoom_moving = False

    # ---- motion loop ---------------------------------------------------------------------
    def _ensure_task(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.ensure_future(self._run())

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            moved = False
            if self._deadline and loop.time() >= self._deadline:
                self._velocity = (0.0, 0.0, 0.0)
                self._deadline = None
            vx, vy, vz = self._velocity
            if any((vx, vy, vz)):
                np_ = _clamp(self.pan + vx * PAN_TILT_UNITS_PER_S * TICK, -1, 1)
                nt = _clamp(self.tilt + vy * PAN_TILT_UNITS_PER_S * TICK, -1, 1)
                nz = _clamp(self.zoom + vz * ZOOM_UNITS_PER_S * TICK, 0, 1)
                moved = (np_, nt, nz) != (self.pan, self.tilt, self.zoom)
                self.pt_moving = (vx or vy) != 0 and (np_, nt) != (self.pan, self.tilt)
                self.zoom_moving = vz != 0 and nz != self.zoom
                self.pan, self.tilt, self.zoom = np_, nt, nz
            elif self._target:
                tp, tt, tz = self._target
                pts, zs = self._target_speed
                step_pt = pts * PAN_TILT_UNITS_PER_S * TICK
                step_z = zs * ZOOM_UNITS_PER_S * TICK
                np_ = self.pan + _clamp(tp - self.pan, -step_pt, step_pt)
                nt = self.tilt + _clamp(tt - self.tilt, -step_pt, step_pt)
                nz = self.zoom + _clamp(tz - self.zoom, -step_z, step_z)
                self.pt_moving = (np_, nt) != (self.pan, self.tilt)
                self.zoom_moving = nz != self.zoom
                moved = self.pt_moving or self.zoom_moving
                self.pan, self.tilt, self.zoom = np_, nt, nz
                if abs(tp - np_) < 1e-6 and abs(tt - nt) < 1e-6 and abs(tz - nz) < 1e-6:
                    self.pan, self.tilt, self.zoom = tp, tt, tz
                    self._target = None
            else:
                self.pt_moving = self.zoom_moving = False
                self._task = None
                return
            if moved:
                self._on_move()
            elif not any(self._velocity) and self._target is None:
                self.pt_moving = self.zoom_moving = False
            await asyncio.sleep(TICK)


def crop_rect(pan: float, tilt: float, zoom: float, width: int, height: int) -> tuple[int, int, int, int]:
    """(w, h, x, y) crop window on a width x height source. zoom 1.0 = 4x digital zoom."""
    f = 1.0 - 0.75 * _clamp(zoom, 0, 1)
    cw = max(16, int(width * f) // 2 * 2)
    ch = max(16, int(height * f) // 2 * 2)
    cx = 0.5 + _clamp(pan, -1, 1) * (1 - f) / 2
    cy = 0.5 - _clamp(tilt, -1, 1) * (1 - f) / 2
    x = int(_clamp(cx * width - cw / 2, 0, width - cw))
    y = int(_clamp(cy * height - ch / 2, 0, height - ch))
    return cw, ch, x, y
