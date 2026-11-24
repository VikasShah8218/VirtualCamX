/**
 * Minimal WHEP (WebRTC-HTTP Egress Protocol) reader, same approach as nvr_client.
 * POST an SDP offer to the backend's WHEP proxy, set the SDP answer, play the tracks.
 * Non-trickle: wait for local ICE gathering so one request is enough.
 */
export interface WhepSession {
  pc: RTCPeerConnection
  close: () => void
}

function waitIceGathering(pc: RTCPeerConnection, timeoutMs: number): Promise<void> {
  if (pc.iceGatheringState === "complete") return Promise.resolve()
  return new Promise((resolve) => {
    const done = () => {
      pc.removeEventListener("icegatheringstatechange", check)
      clearTimeout(timer)
      resolve()
    }
    const check = () => pc.iceGatheringState === "complete" && done()
    const timer = setTimeout(done, timeoutMs)
    pc.addEventListener("icegatheringstatechange", check)
  })
}

function waitConnected(pc: RTCPeerConnection, timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("WebRTC connection timed out (UDP blocked?)")), timeoutMs)
    const check = () => {
      if (pc.connectionState === "connected") {
        clearTimeout(timer)
        resolve()
      } else if (pc.connectionState === "failed" || pc.connectionState === "closed") {
        clearTimeout(timer)
        reject(new Error(`WebRTC ${pc.connectionState}`))
      }
    }
    pc.addEventListener("connectionstatechange", check)
    check()
  })
}

export async function startWhep(
  whepUrl: string,
  video: HTMLVideoElement,
  opts: { headers?: Record<string, string>; timeoutMs?: number } = {},
): Promise<WhepSession> {
  const timeoutMs = opts.timeoutMs ?? 12_000
  const pc = new RTCPeerConnection()
  let sessionUrl: string | null = null
  const close = () => {
    pc.close()
    if (sessionUrl) fetch(sessionUrl, { method: "DELETE", keepalive: true }).catch(() => {})
  }
  try {
    pc.addTransceiver("video", { direction: "recvonly" })
    pc.addTransceiver("audio", { direction: "recvonly" })
    const stream = new MediaStream()
    pc.ontrack = (ev) => {
      stream.addTrack(ev.track)
      if (video.srcObject !== stream) video.srcObject = stream
    }
    await pc.setLocalDescription(await pc.createOffer())
    await waitIceGathering(pc, 1500)

    const controller = new AbortController()
    const abort = setTimeout(() => controller.abort(), timeoutMs)
    let res: Response
    try {
      res = await fetch(whepUrl, {
        method: "POST",
        headers: { "Content-Type": "application/sdp", ...(opts.headers ?? {}) },
        body: pc.localDescription!.sdp,
        signal: controller.signal,
        credentials: "same-origin",
      })
    } finally {
      clearTimeout(abort)
    }
    if (!res.ok) {
      throw new Error(res.status === 404 ? "Stream not available (camera stopped or offline?)" : res.status === 401 ? "Not signed in" : `WHEP HTTP ${res.status}`)
    }
    const location = res.headers.get("Location")
    if (location) sessionUrl = new URL(location, window.location.href).toString()
    await pc.setRemoteDescription({ type: "answer", sdp: await res.text() })
    await waitConnected(pc, timeoutMs)
    return { pc, close }
  } catch (err) {
    close()
    throw err
  }
}

export interface InboundStats {
  width?: number
  height?: number
  fps?: number
  kbps?: number
  codec?: string
  delayMs?: number
}

/** Video stats from getStats(); call twice (prev -> now) to get a bitrate. */
export async function inboundStats(pc: RTCPeerConnection, prev?: { bytes: number; t: number }) {
  const stats = await pc.getStats()
  const out: InboundStats = {}
  let bytes = 0
  let codecId: string | undefined
  stats.forEach((s) => {
    if (s.type === "inbound-rtp" && s.kind === "video") {
      out.width = s.frameWidth
      out.height = s.frameHeight
      out.fps = s.framesPerSecond
      bytes = s.bytesReceived
      codecId = s.codecId
      if (s.jitterBufferEmittedCount > 0) out.delayMs = Math.round((s.jitterBufferDelay / s.jitterBufferEmittedCount) * 1000)
    }
  })
  if (codecId) {
    const c = stats.get(codecId)
    if (c?.mimeType) out.codec = String(c.mimeType).replace("video/", "")
  }
  const now = performance.now()
  if (prev && now > prev.t) out.kbps = ((bytes - prev.bytes) * 8) / (now - prev.t)
  return { stats: out, mark: { bytes, t: now } }
}
