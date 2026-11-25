"""All settings for vcam_server. Values come from `.env` next to main.py.

Nothing else in the code reads environment variables directly (see doc/CODING_STYLE.md).
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parents[1]  # .../vcam_server


class VcamSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=SERVICE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # ---- Server -------------------------------------------------------------------------
    manager_host: str = "0.0.0.0"
    manager_port: int = 9000
    host_ip: str = ""  # IP advertised to NVRs in Port Mode; empty = auto-detect
    wsd_interface_ip: str = ""  # NIC used for WS-Discovery multicast; empty = host_ip
    data_dir: Path = Path("data")
    bin_dir: Path = Path("bin")  # relative paths are relative to vcam_server/
    log_level: str = "INFO"

    # ---- Security -----------------------------------------------------------------------
    secret_key: str = "change-me-please-change-me-please"
    manager_auth_enabled: bool = True
    admin_default_user: str = "admin"
    admin_default_password: str = "admin"
    access_token_minutes: int = 12 * 60

    # ---- Cameras ------------------------------------------------------------------------
    addr_mode: Literal["port", "ip"] = "port"
    cam_port_range: str = "8001-8999"
    cam_ip_range: str = "192.168.1.201-192.168.1.250"
    cam_bind_host: str = "0.0.0.0"  # Port Mode listeners bind here
    cam_default_user: str = "admin"
    cam_default_password: str = "admin123"
    reboot_seconds: int = 20
    start_batch_size: int = 10

    # ---- Media --------------------------------------------------------------------------
    mediamtx_rtsp_port: int = 8554
    rtsp_transports: str = "udp,multicast,tcp"  # "tcp" behind NAT (Docker bridge)
    mediamtx_rtp_port: int = 8000  # RTSP over UDP: RTP on this port, RTCP on +1 (UDP)
    mediamtx_multicast_port: int = 8002  # RTSP multicast: RTP on this port, RTCP on +1 (UDP)
    mediamtx_webrtc_port: int = 8889
    mediamtx_webrtc_udp_port: int = 8189
    mediamtx_api_port: int = 9997
    zmq_base_port: int = 21000
    cache_job_workers: int = 2
    snapshot_max_parallel: int = 4
    x264_preset: str = "veryfast"

    # ---- ONVIF --------------------------------------------------------------------------
    wssec_time_tolerance_s: int = 300  # 0 disables the Created-time check
    max_subscriptions_per_camera: int = 20
    inspector_buffer_per_camera: int = 2000
    wsd_enabled: bool = True

    # ---- Derived helpers ----------------------------------------------------------------
    @property
    def port_range(self) -> tuple[int, int]:
        lo, hi = self.cam_port_range.split("-")
        return int(lo), int(hi)

    @property
    def ffmpeg_path(self) -> str:
        return _find_binary(self.bin_dir, "ffmpeg")

    @property
    def ffprobe_path(self) -> str:
        return _find_binary(self.bin_dir, "ffprobe")

    @property
    def mediamtx_path(self) -> str:
        return _find_binary(self.bin_dir, "mediamtx")

    @property
    def reserved_ports(self) -> set[int]:
        return {
            self.manager_port,
            self.mediamtx_rtsp_port,
            self.mediamtx_webrtc_port,
            self.mediamtx_api_port,
            # MediaMTX RTP/RTCP/multicast (UDP, kept free to avoid confusion)
            self.mediamtx_rtp_port, self.mediamtx_rtp_port + 1,
            self.mediamtx_multicast_port, self.mediamtx_multicast_port + 1,
            8322,  # RTSPS
        }


def _find_binary(bin_dir: Path, name: str) -> str:
    """Prefer bin/<name>(.exe); otherwise rely on PATH."""
    import shutil

    for candidate in (bin_dir / f"{name}.exe", bin_dir / name):
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(name)
    return found or name


@lru_cache
def get_settings() -> VcamSettings:
    s = VcamSettings()
    s.data_dir = (SERVICE_DIR / s.data_dir).resolve()  # absolute paths in .env stay as they are
    s.bin_dir = (SERVICE_DIR / s.bin_dir).resolve()
    return s


settings = get_settings()
