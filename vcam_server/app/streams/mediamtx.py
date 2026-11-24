"""MediaMTX: owned child process + control API client.

vcam_server writes data/mediamtx.yml (JSON is valid YAML), starts bin/mediamtx, and keeps
the RTSP users in sync with the camera users (authMethod: internal, so RTSP Digest works).
"""
import asyncio
import json
import logging
import secrets
from collections import deque
from collections.abc import Callable

import httpx

from settings.settings import settings
from utilities import procutil

logger = logging.getLogger("vcam.mediamtx")


class MediaMtx:
    def __init__(self, users_provider: Callable[[], list[dict]]):
        self.users_provider = users_provider  # -> [{"user","pass","paths":[prefix,...]}]
        self.proc: asyncio.subprocess.Process | None = None
        self.publisher_user = "vcam_pub"
        self.publisher_pass = secrets.token_hex(12)
        self.api = httpx.AsyncClient(base_url=f"http://127.0.0.1:{settings.mediamtx_api_port}", timeout=5.0)
        self.log_tail: deque[str] = deque(maxlen=200)
        self._stderr_task: asyncio.Task | None = None
        self.restarts = 0
        self._sync_lock = asyncio.Lock()
        self._last_users: list | None = None

    # ---- config ----------------------------------------------------------------------------
    def publish_base(self) -> str:
        return f"rtsp://{self.publisher_user}:{self.publisher_pass}@127.0.0.1:{settings.mediamtx_rtsp_port}"

    def internal_read_base(self) -> str:
        return self.publish_base()

    def _auth_users(self) -> list[dict]:
        local = ["127.0.0.1", "::1"]
        users = [
            {
                "user": self.publisher_user,
                "pass": self.publisher_pass,
                "ips": local,
                "permissions": [{"action": "publish"}, {"action": "read"}, {"action": "playback"}],
            },
            {"user": "any", "pass": "", "ips": local, "permissions": [{"action": "api"}, {"action": "metrics"}]},
        ]
        # Group identical credentials so 200 cameras with admin/admin123 become one entry
        grouped: dict[tuple[str, str], list[str]] = {}
        for u in self.users_provider():
            grouped.setdefault((u["user"], u["pass"]), []).extend(u["paths"])
        for (user, pw), prefixes in sorted(grouped.items()):
            users.append(
                {
                    "user": user,
                    "pass": pw,
                    "ips": [],
                    "permissions": [{"action": "read", "path": f"~^({'|'.join(sorted(set(prefixes)))})/"}],
                }
            )
        return users

    def build_config(self) -> dict:
        port_mode = settings.addr_mode == "port"
        return {
            "logLevel": "warn",
            "logDestinations": ["stdout"],
            "readTimeout": "10s",
            "writeTimeout": "10s",
            "writeQueueSize": 1024,
            "authMethod": "internal",
            "authInternalUsers": self._auth_users(),
            "api": True,
            "apiAddress": f"127.0.0.1:{settings.mediamtx_api_port}",
            "metrics": False,
            "pprof": False,
            "playback": False,
            "rtsp": True,
            "rtspTransports": ["udp", "multicast", "tcp"],
            "rtspAddress": f":{settings.mediamtx_rtsp_port if port_mode else 554}",
            "rtspAuthMethods": ["basic", "digest"],
            "rtmp": False,
            "hls": False,
            "srt": False,
            "moq": False,
            "webrtc": True,
            "webrtcAddress": f":{settings.mediamtx_webrtc_port}",
            "webrtcLocalUDPAddress": f":{settings.mediamtx_webrtc_udp_port}",
            "webrtcAllowOrigins": ["*"],
            "pathDefaults": {"source": "publisher", "overridePublisher": True},
            "paths": {"all_others": {}},
        }

    # ---- process ---------------------------------------------------------------------------
    async def start(self) -> None:
        cfg_path = settings.data_dir / "mediamtx.yml"
        cfg_path.write_text(json.dumps(self.build_config(), indent=2), encoding="utf-8")
        self._last_users = self._auth_users()
        self.proc = await procutil.start_process(
            [settings.mediamtx_path, str(cfg_path)], cwd=str(settings.data_dir), merge_output=True
        )
        self._stderr_task = asyncio.ensure_future(self._read_output())
        for _ in range(50):
            if self.proc.returncode is not None:
                break
            try:
                r = await self.api.get("/v3/config/global/get")
                if r.status_code == 200:
                    logger.info("MediaMTX ready (pid %s, RTSP :%s)", self.proc.pid, settings.mediamtx_rtsp_port)
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)
        raise RuntimeError("MediaMTX did not start: " + " | ".join(list(self.log_tail)[-5:]))

    async def _read_output(self) -> None:
        assert self.proc and self.proc.stdout
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                return
            txt = line.decode("utf-8", "replace").rstrip()
            self.log_tail.append(txt)
            if " ERR " in txt or "ERR" in txt[:30]:
                logger.warning("mediamtx: %s", txt)

    def running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def stop(self) -> None:
        if self.proc:
            await procutil.stop_process(self.proc, graceful_input=None, timeout=0.1)
        if self._stderr_task:
            self._stderr_task.cancel()
        await self.api.aclose()

    async def watchdog(self) -> bool:
        """Restart MediaMTX if it died. Returns True if a restart happened."""
        if self.running():
            return False
        logger.error("MediaMTX is not running; restarting")
        self.restarts += 1
        await self.start()
        return True

    # ---- API -------------------------------------------------------------------------------
    async def sync_users(self) -> None:
        async with self._sync_lock:
            users = self._auth_users()
            if users == self._last_users or not self.running():
                return
            r = await self.api.patch("/v3/config/global/patch", json={"authInternalUsers": users})
            if r.status_code >= 300:
                logger.error("MediaMTX user sync failed: %s %s", r.status_code, r.text[:200])
                return
            self._last_users = users

    async def list_paths(self) -> list[dict]:
        r = await self.api.get("/v3/paths/list", params={"itemsPerPage": 10000})
        r.raise_for_status()
        return r.json().get("items", [])

    async def list_rtsp_sessions(self) -> list[dict]:
        r = await self.api.get("/v3/rtspsessions/list", params={"itemsPerPage": 10000})
        r.raise_for_status()
        return r.json().get("items", [])

    async def kick_rtsp_session(self, session_id: str) -> None:
        await self.api.post(f"/v3/rtspsessions/kick/{session_id}")

    async def kick_readers(self, path_prefix: str) -> int:
        n = 0
        for s in await self.list_rtsp_sessions():
            if s.get("state") == "read" and str(s.get("path", "")).startswith(path_prefix + "/"):
                await self.kick_rtsp_session(s["id"])
                n += 1
        return n
