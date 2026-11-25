# syntax=docker/dockerfile:1.7
#
# VirtualCamX - one image with everything: web UI, backend, MediaMTX and FFmpeg.
#
# Build context is the repository root:
#   docker build -f deploy/Dockerfile -t vcamx:latest .
# (or just `docker compose up -d --build` from the deploy/ folder)

ARG PYTHON_VERSION=3.13
ARG NODE_VERSION=22
ARG MEDIAMTX_VERSION=v1.21.2

# ---------------------------------------------------------------------------------------
# Stage 1: build the web client (React + Vite) -> /src/vcam_server/static/web
# ---------------------------------------------------------------------------------------
FROM node:${NODE_VERSION}-bookworm-slim AS web
WORKDIR /src/vcam_client
COPY vcam_client/package.json vcam_client/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY vcam_client/ ./
# vite.config.ts writes the build to ../vcam_server/static/web
RUN npm run build

# ---------------------------------------------------------------------------------------
# Stage 2: download MediaMTX for the target CPU (amd64 / arm64)
# ---------------------------------------------------------------------------------------
FROM debian:bookworm-slim AS mediamtx
ARG MEDIAMTX_VERSION
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    curl -fsSL -o /tmp/mtx.tar.gz \
      "https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/mediamtx_${MEDIAMTX_VERSION}_linux_${TARGETARCH}.tar.gz"; \
    mkdir -p /out; \
    tar -xzf /tmp/mtx.tar.gz -C /out mediamtx LICENSE; \
    /out/mediamtx --version || true

# ---------------------------------------------------------------------------------------
# Stage 3: runtime
# ---------------------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="VirtualCamX" \
      org.opencontainers.image.description="Farm of virtual ONVIF IP cameras for NVR testing" \
      org.opencontainers.image.source="https://github.com/" \
      org.opencontainers.image.licenses="Proprietary"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=UTC \
    # Container paths (override what a shared .env may say for a local Windows run)
    DATA_DIR=/data \
    BIN_DIR=/app/bin \
    MANAGER_HOST=0.0.0.0

# FFmpeg (Debian build has libx264, libx265, drawtext and the zmq filter),
# a font for the OSD, and tzdata for camera clocks.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        tzdata \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY vcam_server/requirements.txt ./requirements.txt
# Runtime deps only (the test tools at the bottom of requirements.txt are skipped)
RUN sed -n '/^# tests/q;p' requirements.txt > requirements.runtime.txt \
    && pip install -r requirements.runtime.txt

COPY vcam_server/ ./
COPY --from=web /src/vcam_server/static/web ./static/web
COPY --from=mediamtx /out/mediamtx /out/LICENSE ./bin/

# Non-root user; /data holds the database, logs, snapshots and caches; /media is for footage
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin vcamx \
    && mkdir -p /data /media \
    && chown -R vcamx:vcamx /data /app/bin
USER vcamx

VOLUME ["/data"]

# Manager UI/API, RTSP, WebRTC (HTTP + UDP), RTP/RTCP, camera ports
EXPOSE 9000 8554 8889 8189/udp 8000/udp 8001/udp 8004-8999 3702/udp

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"MANAGER_PORT\",\"9000\")}/api/v1/system/health', timeout=4)" || exit 1

STOPSIGNAL SIGTERM
CMD ["python", "main.py"]
