import { Activity, ImageIcon, Loader2, RefreshCw, VideoOff } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { inboundStats, startWhep, type InboundStats, type WhepSession } from "@/lib/whep"

/**
 * Live video for one camera stream.
 * - WebRTC (WHEP) through the backend proxy; plays only while visible on screen.
 * - At most MAX_SESSIONS WebRTC sessions per browser tab; beyond that (or when WebRTC fails)
 *   it shows a JPEG snapshot refreshed every 2 s, if `snapshotUrl` is given.
 */
const MAX_SESSIONS = 16
let activeSessions = 0

type Phase = "idle" | "connecting" | "playing" | "snapshot" | "error"

export function LivePlayer({ whepUrl, headers, snapshotUrl, label, className, overlay, fit = "contain", onPlaying }: {
  whepUrl: string
  headers?: Record<string, string>
  snapshotUrl?: (bust: number) => string
  label?: string
  className?: string
  overlay?: boolean
  fit?: "contain" | "cover"
  onPlaying?: (pc: RTCPeerConnection) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const video = useRef<HTMLVideoElement>(null)
  const session = useRef<WhepSession | null>(null)
  const counted = useRef(false)
  const [visible, setVisible] = useState(false)
  const [phase, setPhase] = useState<Phase>("idle")
  const [error, setError] = useState<string | null>(null)
  const [retryIn, setRetryIn] = useState(0)
  const [attempt, setAttempt] = useState(0)
  const [bust, setBust] = useState(() => Date.now())
  const [stats, setStats] = useState<InboundStats | null>(null)
  const headersKey = JSON.stringify(headers ?? {})
  // Callbacks are often inline arrows (new every render): keep them in refs so they never restart the stream
  const snapshotRef = useRef(snapshotUrl)
  snapshotRef.current = snapshotUrl
  const onPlayingRef = useRef(onPlaying)
  onPlayingRef.current = onPlaying
  const hasSnapshot = !!snapshotUrl

  // Only play while on screen (live walls with many tiles)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0.05 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  const stop = useCallback(() => {
    session.current?.close()
    session.current = null
    if (counted.current) {
      activeSessions--
      counted.current = false
    }
  }, [])

  useEffect(() => {
    if (!visible) {
      stop()
      setPhase("idle")
      return
    }
    if (activeSessions >= MAX_SESSIONS) {
      setPhase(hasSnapshot ? "snapshot" : "error")
      setError(hasSnapshot ? null : `More than ${MAX_SESSIONS} live videos open`)
      return
    }
    let cancelled = false
    activeSessions++
    counted.current = true
    setPhase("connecting")
    setError(null)
    startWhep(whepUrl, video.current!, { headers: JSON.parse(headersKey) })
      .then((s) => {
        if (cancelled) return s.close()
        session.current = s
        setPhase("playing")
        onPlayingRef.current?.(s.pc)
        s.pc.addEventListener("connectionstatechange", () => {
          if (s.pc.connectionState === "failed" || s.pc.connectionState === "disconnected") {
            setError("Connection lost")
            setPhase("error")
          }
        })
      })
      .catch((e: Error) => {
        if (cancelled) return
        stop()
        setError(e.message)
        setPhase(hasSnapshot ? "snapshot" : "error")
      })
    return () => {
      cancelled = true
      stop()
    }
  }, [visible, whepUrl, headersKey, attempt, stop, hasSnapshot])

  // Auto-retry: after an error (or while in snapshot fallback) try WebRTC again every 10 s
  useEffect(() => {
    if (phase !== "error" && !(phase === "snapshot" && error)) return
    setRetryIn(10)
    const t = setInterval(() => {
      setRetryIn((s) => {
        if (s <= 1) {
          clearInterval(t)
          setAttempt((a) => a + 1)
          return 0
        }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(t)
  }, [phase, error])

  // Snapshot refresh
  useEffect(() => {
    if (phase !== "snapshot" || !visible) return
    const t = setInterval(() => setBust(Date.now()), 2000)
    return () => clearInterval(t)
  }, [phase, visible])

  // Stats overlay
  useEffect(() => {
    if (!overlay || phase !== "playing" || !session.current) return
    let mark: { bytes: number; t: number } | undefined
    const tick = async () => {
      if (!session.current) return
      const r = await inboundStats(session.current.pc, mark)
      mark = r.mark
      setStats(r.stats)
    }
    void tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [overlay, phase])

  return (
    <div ref={box} className={cn("relative overflow-hidden rounded-lg bg-video", className)}>
      <video
        ref={video}
        autoPlay
        muted
        playsInline
        className={cn("size-full", fit === "cover" ? "object-cover" : "object-contain", phase !== "playing" && "invisible")}
      />
      {phase === "snapshot" && snapshotRef.current && (
        <img src={snapshotRef.current(bust)} alt={label ?? "snapshot"} className={cn("absolute inset-0 size-full", fit === "cover" ? "object-cover" : "object-contain")} />
      )}

      {(phase === "connecting" || phase === "idle") && (
        <div className="absolute inset-0 grid place-items-center text-xs text-muted-foreground">
          <span className="flex items-center gap-2"><Loader2 className="size-4 animate-spin" /> Connecting…</span>
        </div>
      )}
      {phase === "error" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-3 text-center text-xs text-muted-foreground">
          <VideoOff className="size-6" />
          <span className="max-w-xs">{error}</span>
          <Button variant="outline" size="xs" onClick={() => setAttempt((a) => a + 1)}>
            <RefreshCw /> Retry{retryIn ? ` (${retryIn})` : ""}
          </Button>
        </div>
      )}

      {label && (
        <div className="pointer-events-none absolute top-1.5 left-1.5 rounded bg-background/70 px-1.5 py-0.5 text-[11px] font-medium">{label}</div>
      )}
      {phase === "snapshot" && (
        <div className="absolute right-1.5 bottom-1.5 flex items-center gap-1 rounded bg-background/70 px-1.5 py-0.5 text-[10px] text-muted-foreground" title={error ?? "Snapshot mode"}>
          <ImageIcon className="size-3" /> snapshot{retryIn ? ` · live in ${retryIn}s` : ""}
        </div>
      )}
      {overlay && phase === "playing" && stats && (
        <div className="pointer-events-none absolute right-1.5 bottom-1.5 flex items-center gap-1.5 rounded bg-background/75 px-2 py-1 font-mono text-[10px] tabular-nums">
          <Activity className="size-3 text-success" />
          {stats.width}×{stats.height} · {Math.round(stats.fps ?? 0)} fps · {stats.kbps ? `${(stats.kbps / 1000).toFixed(1)} Mbps` : "…"}
          {stats.codec ? ` · ${stats.codec}` : ""}
          {stats.delayMs != null ? ` · ${stats.delayMs} ms` : ""}
        </div>
      )}
    </div>
  )
}
