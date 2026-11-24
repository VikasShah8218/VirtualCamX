"""Active faults of one camera (runtime side). Applying/clearing lives in faults/services.py."""
from dataclasses import dataclass, field
from datetime import datetime

FAULT_TYPES: dict[str, dict] = {
    "offline": {"label": "Camera offline", "desc": "ONVIF/HTTP port closed and RTSP stopped", "params": {}},
    "stream_drop": {"label": "Stream drop", "desc": "Kick all RTSP clients (optionally every N s)", "params": {"repeat_every_s": 0}},
    "reboot": {"label": "Reboot", "desc": "Offline for N seconds, then back with a new boot time", "params": {"seconds": 20}},
    "freeze": {"label": "Video freeze", "desc": "Stream continues but the picture stops changing", "params": {}},
    "black": {"label": "Video loss", "desc": "Black frames + SignalLoss event", "params": {}},
    "clock_drift": {"label": "Clock drift", "desc": "Camera time is off by N seconds", "params": {"offset_s": 600}},
    "slow_onvif": {"label": "Slow ONVIF", "desc": "Delay every SOAP response", "params": {"delay_ms": 3000}},
    "password_changed": {"label": "Password changed", "desc": "All logins fail with NotAuthorized", "params": {}},
    "flapping": {"label": "Flapping", "desc": "Goes offline/online on a schedule", "params": {"offline_s": 10, "online_s": 30}},
    "onvif_error": {"label": "ONVIF error", "desc": "Return a SOAP fault for selected operations", "params": {"operations": ["GetStreamUri"]}},
}


@dataclass
class ActiveFault:
    id: int
    type: str
    params: dict
    started_at: datetime
    expires_at: datetime | None = None
    runtime: dict = field(default_factory=dict)  # scratch data for loops (next toggle time...)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "params": self.params,
            "started_at": self.started_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class FaultSet:
    def __init__(self):
        self.active: dict[str, ActiveFault] = {}
        self.freeze_file: str | None = None  # relative to data dir

    def has(self, kind: str) -> bool:
        return kind in self.active

    def video_override(self) -> str | None:
        if "black" in self.active:
            return "black"
        if "freeze" in self.active:
            return "freeze"
        return None

    def onvif_delay_ms(self) -> int:
        f = self.active.get("slow_onvif")
        return int(f.params.get("delay_ms", 3000)) if f else 0

    def onvif_error_for(self, op: str) -> bool:
        f = self.active.get("onvif_error")
        return bool(f) and op in (f.params.get("operations") or [])

    def auth_broken(self) -> bool:
        return "password_changed" in self.active

    def list(self) -> list[dict]:
        return [f.to_json() for f in self.active.values()]
