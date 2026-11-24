"""CameraRuntime: one live virtual camera (state, listener, stream, events, PTZ, faults)."""
import asyncio
import logging
import os
import re
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from app.cameras.state import CameraState
from app.events.broker import EventBroker
from app.faults.state import FaultSet
from app.onvif.security import NonceCache, UserEntry
from app.ptz.controller import PtzController
from app.runtime.clock import CameraClock
from app.runtime.listener import CameraListener
from app.streams.worker import StreamWorker
from app.system import hub
from settings.settings import settings
from utilities.common import utcnow

if TYPE_CHECKING:
    from app.runtime.manager import CameraManager

logger = logging.getLogger("vcam.camera")

# Sections whose change affects the video pipeline
STREAM_SECTIONS = {"source", "stream", "encoders", "imaging", "osd", "video_source", "faults", "ptz_position"}


class CameraStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    REBOOTING = "rebooting"
    OFFLINE = "offline"
    STOPPING = "stopping"
    ERROR = "error"


class CameraRuntime:
    def __init__(self, manager: "CameraManager", record, users: list[UserEntry]):
        self.manager = manager
        self.camera_id: int = record.id
        self.number: int = record.number
        self.name: str = record.name
        self.enabled: bool = record.enabled
        self.template_key: str = record.template_key
        self.addr_mode: str = record.addr_mode
        self.ip: str | None = record.ip
        self.http_port: int = record.http_port
        self.state = CameraState.model_validate(record.state)
        self.users: dict[str, UserEntry] = {u.username: u for u in users}

        self.status = CameraStatus.STOPPED
        self.last_error: str | None = None
        self.boot_time: datetime | None = None
        self.state_version = 0
        self.clock = CameraClock(self.state.time.offset_seconds)
        self.broker = EventBroker(self)
        self.ptz = PtzController(self._on_ptz_move)
        self.ptz.pan, self.ptz.tilt, self.ptz.zoom = self.state.ptz.home_pan, self.state.ptz.home_tilt, self.state.ptz.home_zoom
        self.worker = StreamWorker(self)
        self.faults = FaultSet()
        self.listener: CameraListener | None = None
        self.nonces = NonceCache(max(60, settings.wssec_time_tolerance_s * 2))
        self.logs: deque[str] = deque(maxlen=500)
        self.state_lock = asyncio.Lock()
        self.life_lock = asyncio.Lock()
        self._pulse_handles: dict[str, asyncio.TimerHandle] = {}
        self._osd_event_text = ""
        self._osd_written: dict[str, str] = {}
        self._reboot_task: asyncio.Task | None = None
        self._relay_timers: dict[str, asyncio.TimerHandle] = {}

    # ---- addressing ---------------------------------------------------------------------------
    @property
    def path_prefix(self) -> str:
        return f"cam{self.number:03d}"

    def advertised_ip(self) -> str:
        return self.ip if self.addr_mode == "ip" and self.ip else self.manager.host_ip

    def bind_addr(self) -> tuple[str, int]:
        if self.addr_mode == "ip" and self.ip:
            return self.ip, 80
        return settings.cam_bind_host, self.http_port

    def http_port_public(self) -> int:
        return 80 if self.addr_mode == "ip" else self.http_port

    def rtsp_port(self) -> int:
        return settings.mediamtx_rtsp_port if self.addr_mode == "port" else 554

    def rtsp_url(self, host: str | None, stream_key: str) -> str:
        host = host or self.advertised_ip()
        port = self.rtsp_port()
        hp = host if port == 554 else f"{host}:{port}"
        return f"rtsp://{hp}/{self.path_prefix}/{stream_key}"

    def urls(self, host: str | None = None) -> dict:
        host = host or self.advertised_ip()
        port = self.http_port_public()
        base = f"http://{host}" if port == 80 else f"http://{host}:{port}"
        return {
            "onvif": f"{base}/onvif/device_service",
            "web": f"{base}/",
            "rtsp": {e.stream_key: self.rtsp_url(host, e.stream_key) for e in self.state.video_encoders},
            "snapshot": {p.token: f"{base}/snapshot/{p.token}.jpg" for p in self.state.profiles},
        }

    # ---- logging -------------------------------------------------------------------------------
    def log(self, msg: str) -> None:
        line = f"{self.clock.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        self.logs.append(line)
        logger.info("[%s] %s", self.name, msg)

    # ---- lifecycle ----------------------------------------------------------------------------
    async def start(self) -> None:
        async with self.life_lock:
            if self.status in (CameraStatus.RUNNING, CameraStatus.STARTING):
                return
            await self._start_locked()

    async def _start_locked(self, final_status: CameraStatus = CameraStatus.RUNNING) -> None:
        self.status = CameraStatus.STARTING
        self.last_error = None
        self.boot_time = utcnow()
        self.broker.reset_properties()
        self.write_osd_files(force=True)
        await self.manager.sync_rtsp_users()
        self.worker.start()
        if self.faults.has("offline"):
            self.status = CameraStatus.OFFLINE
            self._publish_status()
            return
        if not await self._open_listener():
            await self.worker.stop()
            self.status = CameraStatus.ERROR
            self._publish_status()
            return
        self.manager.wsd_hello(self)
        self.status = final_status
        self.log(f"started: {self.urls()['onvif']}")
        self._publish_status()

    async def _open_listener(self) -> bool:
        host, port = self.bind_addr()
        self.listener = CameraListener(self.camera_id, host, port, self.manager.camera_app)
        try:
            await self.listener.start()
            return True
        except OSError as exc:
            self.last_error = f"cannot listen on {host}:{port}: {exc}"
            logger.error("[%s] %s", self.name, self.last_error)
            self.listener = None
            return False

    async def _close_listener(self) -> None:
        if self.listener:
            await self.listener.stop()
            self.listener = None

    async def stop(self, final_status: CameraStatus = CameraStatus.STOPPED) -> None:
        async with self.life_lock:
            await self._stop_locked(final_status)

    async def _stop_locked(self, final_status: CameraStatus) -> None:
        if self.status in (CameraStatus.STOPPED,) and final_status == CameraStatus.STOPPED:
            return
        self.status = CameraStatus.STOPPING
        self.manager.wsd_bye(self)
        await self._close_listener()
        self.broker.close_all()
        self.ptz.shutdown()
        for h in list(self._pulse_handles.values()) + list(self._relay_timers.values()):
            h.cancel()
        self._pulse_handles.clear()
        self._relay_timers.clear()
        await self.worker.stop()
        self.status = final_status
        self.log(f"stopped ({final_status.value})")
        self._publish_status()

    async def restart(self) -> None:
        async with self.life_lock:
            await self._stop_locked(CameraStatus.STOPPED)
            await self._start_locked()

    def request_reboot(self, seconds: float | None = None, delay: float = 1.0) -> None:
        """Reboot in the background (so ONVIF SystemReboot can answer first)."""
        if self._reboot_task and not self._reboot_task.done():
            return
        self._reboot_task = asyncio.ensure_future(self._reboot(seconds if seconds is not None else settings.reboot_seconds, delay))

    async def _reboot(self, seconds: float, delay: float) -> None:
        await asyncio.sleep(delay)
        self.log(f"rebooting ({seconds:g}s)")
        async with self.life_lock:
            await self._stop_locked(CameraStatus.REBOOTING)
        await asyncio.sleep(seconds)
        async with self.life_lock:
            if self.status == CameraStatus.REBOOTING:
                await self._start_locked()

    async def go_offline(self) -> None:
        """Fault: close the port, stop RTSP. State and subscriptions behave like a powered-off camera."""
        async with self.life_lock:
            if self.status in (CameraStatus.RUNNING, CameraStatus.ERROR):
                await self._stop_locked(CameraStatus.OFFLINE)

    async def go_online(self) -> None:
        async with self.life_lock:
            if self.status == CameraStatus.OFFLINE:
                await self._start_locked()

    def _publish_status(self) -> None:
        hub.publish("camera.status", {"camera_id": self.camera_id, "status": self.status.value, "error": self.last_error})

    # ---- state ---------------------------------------------------------------------------------
    async def update(self, mutator: Callable[[CameraState], None], sections: set[str]) -> CameraState:
        """The single write path for camera config (ONVIF, camera web API and Manager API)."""
        async with self.state_lock:
            new = self.state.model_copy(deep=True)
            mutator(new)
            new = CameraState.model_validate(new.model_dump())
            self.state = new
            self.state_version += 1
            self.manager.mark_dirty(self.camera_id)
        self.on_state_changed(sections)
        return self.state

    def on_state_changed(self, sections: set[str]) -> None:
        if "time" in sections:
            self.clock.offset_seconds = self.state.time.offset_seconds
        if "osd" in sections or "time" in sections:
            self.write_osd_files(force=True)
        if sections & STREAM_SECTIONS:
            self.worker.reconcile()
        hub.publish("camera.state", {"camera_id": self.camera_id, "sections": sorted(sections), "version": self.state_version})

    def _on_ptz_move(self) -> None:
        self.worker.push_live()

    # ---- OSD -----------------------------------------------------------------------------------
    def osd_file_rel(self, token: str) -> str:
        return f"osd/{self.path_prefix}_{token}.txt"

    def local_time(self) -> datetime:
        return self.clock.now() + timedelta(hours=tz_offset_hours(self.state.time.tz))

    def write_osd_files(self, force: bool = False) -> None:
        """Called every second by the OSD clock loop (and on OSD changes)."""
        if self.worker.spec is not None and self.worker.spec.mode != "encode" and not force:
            return
        now = self.local_time()
        texts = {}
        for item in self.state.osd:
            if item.kind == "Plain":
                texts[item.token] = item.plain_text or " "
            elif item.kind == "Date":
                texts[item.token] = now.strftime(onvif_fmt_to_strftime(item.date_format))
            elif item.kind == "Time":
                texts[item.token] = now.strftime(onvif_fmt_to_strftime(item.time_format))
            else:
                texts[item.token] = now.strftime(onvif_fmt_to_strftime(f"{item.date_format} {item.time_format}"))
        texts["OSD_EVENT"] = self._osd_event_text or " "
        for token, txt in texts.items():
            if not force and self._osd_written.get(token) == txt:
                continue
            path = os.path.join(settings.data_dir, self.osd_file_rel(token))
            try:
                write_in_place(path, txt)
                self._osd_written[token] = txt
            except OSError:
                pass  # next tick retries

    # ---- events ----------------------------------------------------------------------------------
    def on_event_published(self, key: str, msg) -> None:
        active = []
        for k, label in (("motion_alarm", "MOTION"), ("tamper", "TAMPER"), ("signal_loss", "VIDEO LOSS")):
            v = self.broker.property_value(k, [("Source", self.state.video_source.token)])
            if v and v.get("State") == "true":
                active.append(label)
        for di in self.state.io.inputs:
            v = self.broker.property_value("digital_input", [("InputToken", di.token)])
            if v and v.get("LogicalState") == "true":
                active.append(f"ALARM IN {di.token.rsplit('_', 1)[-1]}")
        self._osd_event_text = "  ".join(active)
        self.write_osd_files()

    def trigger(self, kind: str, state: bool, token: str | None = None, origin: str = "simulator") -> None:
        vs = self.state.video_source.token
        val = "true" if state else "false"
        if kind == "motion":
            vsc = self.state.video_source_configs[0].token if self.state.video_source_configs else "VideoSourceConfig_1"
            self.broker.publish("motion_alarm", [("Source", vs)], [("State", val)], origin)
            self.broker.publish(
                "cell_motion",
                [("VideoSourceConfigurationToken", vsc), ("VideoAnalyticsConfigurationToken", "VideoAnalyticsConfig_1"), ("Rule", "MyMotionDetectorRule")],
                [("IsMotion", val)],
                origin,
            )
        elif kind == "tamper":
            self.broker.publish("tamper", [("Source", vs)], [("State", val)], origin)
        elif kind == "video_loss":
            self.broker.publish("signal_loss", [("Source", vs)], [("State", val)], origin)
        elif kind == "digital_input":
            tokens = [token] if token else [di.token for di in self.state.io.inputs[:1]]
            for t in tokens:
                di = next((d for d in self.state.io.inputs if d.token == t), None)
                if di is None:
                    raise ValueError(f"unknown digital input {t}")
                di.active = state  # runtime value; also persisted on next save
                self.manager.mark_dirty(self.camera_id)
                self.broker.publish("digital_input", [("InputToken", t)], [("LogicalState", val)], origin)
        else:
            raise ValueError(f"unknown event kind {kind}")
        self.log(f"event {kind}{'/' + token if token else ''} = {val} ({origin})")

    def pulse(self, kind: str, duration_s: float, token: str | None = None, origin: str = "simulator") -> None:
        key = f"{kind}:{token}"
        if key in self._pulse_handles:
            self._pulse_handles.pop(key).cancel()
        self.trigger(kind, True, token, origin)
        loop = asyncio.get_running_loop()

        def _end():
            self._pulse_handles.pop(key, None)
            if self.status == CameraStatus.RUNNING:
                self.trigger(kind, False, token, origin)

        self._pulse_handles[key] = loop.call_later(max(0.1, duration_s), _end)

    def set_relay(self, token: str, active: bool, origin: str = "onvif") -> None:
        relay = next((r for r in self.state.io.relays if r.token == token), None)
        if relay is None:
            raise ValueError(f"unknown relay {token}")
        relay.active = active
        self.manager.mark_dirty(self.camera_id)
        self.broker.publish("relay", [("RelayToken", token)], [("LogicalState", "active" if active else "inactive")], origin)
        self.log(f"relay {token} -> {'active' if active else 'inactive'} ({origin})")
        if token in self._relay_timers:
            self._relay_timers.pop(token).cancel()
        if active and relay.mode == "Monostable":
            self._relay_timers[token] = asyncio.get_running_loop().call_later(
                max(0.1, relay.delay_time_s), lambda: self.set_relay(token, False, "monostable")
            )

    # ---- info ----------------------------------------------------------------------------------
    def info(self) -> dict:
        return {
            "id": self.camera_id,
            "number": self.number,
            "name": self.name,
            "enabled": self.enabled,
            "template_key": self.template_key,
            "status": self.status.value,
            "last_error": self.last_error,
            "addr_mode": self.addr_mode,
            "ip": self.advertised_ip(),
            "http_port": self.http_port_public(),
            "boot_time": self.boot_time.isoformat() if self.boot_time else None,
            "source": self.state.source.model_dump(),
            "stream_mode": self.state.stream_mode,
            "streams": [
                {"key": e.stream_key, "encoding": e.encoding, "width": e.width, "height": e.height, "fps": e.fps, "bitrate_kbps": e.bitrate_kbps}
                for e in self.state.video_encoders
            ],
            "urls": self.urls(),
            "worker": self.worker.info(),
            "faults": self.faults.list(),
            "subscriptions": self.broker.count(),
            "has_ptz": self.state.capabilities.has_ptz,
            "identity": self.state.identity.model_dump(),
        }


def write_in_place(path: str, text: str) -> None:
    """Update an OSD text file that FFmpeg's drawtext re-reads while running.

    Never use write-temp-then-os.replace() here: on Windows the old file is briefly
    "delete pending", FFmpeg's open() fails with EACCES and drawtext treats that as fatal
    (the stream dies). Overwrite then truncate keeps the file present and non-empty.
    """
    data = text.encode("utf-8")
    try:
        f = open(path, "r+b")
    except FileNotFoundError:
        f = open(path, "wb")
    with f:
        f.seek(0)
        f.write(data)
        f.truncate()


def tz_offset_hours(tz: str) -> float:
    """POSIX TZ ('IST-5:30', 'CET-1CEST', 'UTC0') -> hours east of UTC. DST rules are ignored."""
    m = re.match(r"^(?:<[^>]+>|[A-Za-z]{3,})([+-]?)(\d{1,2})(?::(\d{2}))?", tz or "")
    if not m:
        return 0.0
    hours = int(m.group(2)) + int(m.group(3) or 0) / 60
    return -hours if m.group(1) != "-" else hours


def onvif_fmt_to_strftime(fmt: str) -> str:
    table = {"yyyy": "%Y", "yy": "%y", "MMMM": "%B", "MMM": "%b", "MM": "%m", "dd": "%d", "HH": "%H", "hh": "%I",
             "mm": "%M", "ss": "%S", "tt": "%p", "M": "%m", "d": "%d", "H": "%H", "h": "%I", "m": "%M", "s": "%S"}
    return re.sub(r"yyyy|yy|MMMM|MMM|MM|dd|HH|hh|mm|ss|tt|M|d|H|h|m|s", lambda mo: table[mo.group(0)], fmt)
