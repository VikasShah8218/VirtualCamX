# Deploying VirtualCamX with Docker

One image contains everything: the web UI, the backend, MediaMTX and FFmpeg
(with x264, x265, drawtext and the zmq filter). Nothing else needs to be installed on the host.

```
deploy/
├── Dockerfile                  multi-stage: build web UI → fetch MediaMTX → Python runtime
├── Dockerfile.dockerignore     keeps the build context small and secret-free
├── docker-compose.yml          Linux host  - host network (recommended, full features)
├── docker-compose.bridge.yml   Docker Desktop (Windows/macOS) - published ports
└── README.md
```

## 1. Settings: one shared file

Docker uses **the same settings file as a normal run**: `vcam_server/.env`.

```bash
cp vcam_server/.env.example vcam_server/.env      # Windows: copy vcam_server\.env.example vcam_server\.env
```

Edit at least:

| Key | Why |
|---|---|
| `SECRET_KEY` | signs logins - make it long and random: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `HOST_IP` | the host's LAN IP that NVRs connect to. Optional on Linux host network, **required** for bridge mode |
| `VCAMX_MEDIA_DIR` | host folder with your footage (mounted read-only at `/media`) |

Compose always forces the container paths (`DATA_DIR=/data`, `BIN_DIR=/app/bin`), so the same
`.env` keeps working for a local Windows run too. Keys under *Docker only* are ignored by the server.

> Always pass `--env-file ../vcam_server/.env` to `docker compose` - that is what lets compose use
> your ports/IP for port mapping. Without it the defaults are used.

## 2a. Linux host (recommended)

```bash
cd deploy
docker compose --env-file ../vcam_server/.env up -d --build
```

Uses `network_mode: host`, so the cameras behave exactly like hardware on the LAN:
WS-Discovery ("Search devices" on the NVR), one port per camera, RTSP over UDP and TCP, WebRTC.
No ports to map.

## 2b. Windows / macOS (Docker Desktop)

Set `HOST_IP` in `vcam_server/.env` to the PC's LAN IP (e.g. `192.168.1.8`), then:

```powershell
cd deploy
docker compose -f docker-compose.bridge.yml --env-file ../vcam_server/.env up -d --build
```

Differences in bridge mode (Docker's NAT is in the way):

| | Host network | Bridge |
|---|---|---|
| WS-Discovery (auto search on the NVR) | ✅ | ❌ add cameras by `IP:port` |
| Cameras | `CAM_PORT_RANGE` (up to ~990) | `DOCKER_CAM_PORTS` (default `8004-8063` = 60) |
| RTSP | UDP + TCP | TCP only (forced; NVRs fall back automatically) |
| WebRTC live view in the browser | ✅ | ✅ (via `HOST_IP`) |

Need more cameras in bridge mode? Raise `DOCKER_CAM_PORTS` (e.g. `8004-8203`); every port is
published, so very large ranges make container start-up slower.

> Docker Desktop 4.34+ can also enable host networking (*Settings → Resources → Network → Enable
> host networking*). With it on, `docker-compose.yml` works on Windows/macOS too.

## 3. Open it

`http://<HOST_IP>:9000` - log in with `admin` / `admin` (you must change it at first login).
New cameras use `admin` / `admin123`.

**Footage:** put videos in the folder set by `VCAMX_MEDIA_DIR` (default `deploy/media/`), then pick
them in the UI under **/media/...** (Source tab → Browse, or the Media page).

## 4. Day-to-day

Add `-f docker-compose.bridge.yml` to each command in bridge mode.

```bash
docker compose --env-file ../vcam_server/.env ps            # status (shows "healthy")
docker compose --env-file ../vcam_server/.env logs -f       # live logs
docker compose --env-file ../vcam_server/.env restart       # after editing .env
docker compose --env-file ../vcam_server/.env up -d --build # after pulling new code
docker compose --env-file ../vcam_server/.env down         # stop (data is kept)
```

## 5. Data and backups

Everything the server writes (database, logs, snapshots, caches) lives in the named volume
`vcamx_vcamx-data`, mounted at `/data`. It survives `down`, `up --build` and image updates.

```bash
# backup
docker run --rm -v vcamx_vcamx-data:/data -v "$PWD":/backup debian:bookworm-slim \
  tar czf /backup/vcamx-data.tgz -C /data .
# restore (container stopped)
docker run --rm -v vcamx_vcamx-data:/data -v "$PWD":/backup debian:bookworm-slim \
  tar xzf /backup/vcamx-data.tgz -C /data
```

`docker compose down -v` **deletes** the volume - all cameras and settings.

## 6. Image details

| | |
|---|---|
| Base | `python:3.13-slim-bookworm` |
| FFmpeg | Debian 12 package (libx264, libx265, drawtext, zmq) |
| MediaMTX | `v1.21.2`, downloaded for the build platform (`amd64` / `arm64`) |
| User | non-root `vcamx` (uid 10001) |
| Volumes | `/data` (state), `/media` (footage, read-only) |
| Health check | `GET /api/v1/system/health` every 30 s |
| Shutdown | `SIGTERM` → cameras stop gracefully (30 s grace), `init` reaps child processes |

Build arguments: `PYTHON_VERSION`, `NODE_VERSION`, `MEDIAMTX_VERSION`.

```bash
# build only (from the repo root)
docker build -f deploy/Dockerfile -t vcamx:1.0.0 .
# multi-arch
docker buildx build -f deploy/Dockerfile --platform linux/amd64,linux/arm64 -t <registry>/vcamx:1.0.0 --push .
```

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `Set HOST_IP in vcam_server/.env…` | bridge mode needs `HOST_IP`, and `--env-file ../vcam_server/.env` |
| `listen udp :8000: bind` | another MediaMTX (e.g. an NVR's) runs on this PC: set `MEDIAMTX_RTP_PORT`, `MEDIAMTX_RTSP_PORT`, `MEDIAMTX_WEBRTC_PORT`, `MEDIAMTX_WEBRTC_UDP_PORT`, `MEDIAMTX_API_PORT` to free ports |
| `port is already allocated` / `WinError 10048` | VirtualCamX is already running locally (or another app uses the port) - stop it first |
| NVR finds no cameras | bridge mode has no discovery: add by `IP:port`. Host mode: check the firewall allows UDP 3702 |
| NVR adds the camera but shows no video | in bridge mode make sure the NVR can use RTSP over TCP |
| Browser shows snapshots instead of live video | allow UDP `MEDIAMTX_WEBRTC_UDP_PORT` (8189) in the host firewall; check `HOST_IP` |
| Footage path not found | use the path **inside** the container: `/media/<file>` |
| Health / FFmpeg features | `http://<HOST_IP>:9000/api/v1/system/health` or Settings → Server |
