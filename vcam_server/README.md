# vcam_server — VirtualCamX backend

One Python process that runs a farm of virtual ONVIF IP cameras for NVR testing.
Spec: `../doc/VCAMX_FEATURE_SPEC.md` · Architecture & plan: `../plan/BACKEND_IMPLEMENTATION_PLAN.md`

## Run

```
workon vcam                 # virtualenv with requirements.txt installed
cd vcam_server
copy .env.example .env      # first time only; set SECRET_KEY, HOST_IP if needed
py main.py
```

Needs `bin/mediamtx(.exe)` (in `vcam_server/bin/`) and FFmpeg/ffprobe (in `bin/` or on PATH,
a build with `libx264`, `libx265` and the `zmq` filter, e.g. gyan.dev "full").
`GET http://<host>:9000/api/v1/system/health` shows what was found.

| Port | What |
|---|---|
| 9000 | Manager REST API + WebSocket (`/docs` = Swagger UI) |
| 8001–8999 | One port per camera: ONVIF (`/onvif/device_service`), snapshot, camera web API (Port Mode) |
| 8554 | RTSP for all cameras: `rtsp://<host>:8554/camNNN/main|sub|third` |
| 8889 | WebRTC (MediaMTX; the browser goes through the WHEP proxy) |
| 3702/udp | WS-Discovery |

Default logins: Manager `admin` / `admin` (change it). New cameras: `admin` / `admin123` (`CAM_DEFAULT_*`).

## Quick use (API)

```
POST /api/v1/auth/login                {"username":"admin","password":"admin"}  -> access_token
POST /api/v1/cameras                   {"name":"Gate-1","template_key":"bullet_2mp"}
POST /api/v1/cameras/bulk              {"count":50,"template_key":"bullet_2mp","name_pattern":"Lab-{n:03d}",
                                        "stream_mode":"passthrough","source":{"type":"file","path":"D:\\Footage\\gate.mp4"},
                                        "offset_step_s":0.5}
PUT  /api/v1/cameras/{id}/source       {"source":{"type":"file","path":"D:\\Footage\\night.mp4"}}   (live switch)
POST /api/v1/cameras/{id}/events/trigger {"kind":"motion","duration_s":10}
POST /api/v1/cameras/{id}/faults       {"type":"offline","duration_s":30}
GET  /api/v1/inspector?camera_id={id}  every ONVIF request the NVR made (GET /inspector/{entry} for the XML)
```
Templates: `bullet_2mp`, `bullet_4mp`, `dome_5mp`, `ptz_2mp`, `lowend_720p` (`GET /api/v1/templates`).
Full list of endpoints: `http://<host>:9000/docs`.

## Tools & tests

```
py tools/onvif_smoke.py <host> <port> [user] [pass] [--manager URL --token JWT --camera-id N]   # acts like an NVR
py tools/wsd_probe.py [seconds] [interface_ip]                                                 # "search cameras"
pytest                                    # unit tests
set VCAM_IT=192.168.1.17:8005 && pytest -m integration                                         # against a running camera
```

## Status (v1.0 backend)

Done and tested: Port Mode, templates, single/bulk create, ONVIF Device / Media (S) / Media2 (T) / Events
(PullPoint + push) / Imaging / PTZ / DeviceIO, WS-Security + HTTP Digest, WS-Discovery, test-pattern / file /
image / RTSP-relay sources, footage by path with live switching, Encode + Passthrough (auto cache) modes,
live imaging + ePTZ via ZMQ, OSD (clock, name, event alerts), snapshots, event simulator (manual, scheduled,
random, bulk), faults (offline, stream drop, reboot, freeze, video loss, clock drift, slow ONVIF, password
changed, flapping, ONVIF error), ONVIF Inspector, camera web API, Manager API + WebSocket, restart persistence.

Not done yet (P1/P2 in the spec): IP Mode alias management (`network/`), HTTPS, audio, multicast, folder
playlists, shared passthrough feeds (each passthrough camera runs its own `-c copy` FFmpeg, ~0.04 cores),
privacy masks, Profile G/M, the web client (separate plan).
