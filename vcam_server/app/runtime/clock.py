from datetime import datetime, timedelta, timezone

from utilities.common import utcnow


class CameraClock:
    """Camera time = host UTC + offset (set by SetSystemDateAndTime) + fault offset (clock drift)."""

    def __init__(self, offset_seconds: float = 0.0):
        self.offset_seconds = offset_seconds
        self.fault_offset = 0.0

    def now(self) -> datetime:
        return utcnow() + timedelta(seconds=self.offset_seconds + self.fault_offset)

    def set_manual(self, camera_utc: datetime) -> float:
        """Set the camera clock to `camera_utc`; returns the new offset to persist."""
        self.offset_seconds = (camera_utc.astimezone(timezone.utc) - utcnow()).total_seconds()
        return self.offset_seconds

    def reset(self) -> None:
        self.offset_seconds = 0.0
