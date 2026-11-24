/**
 * Manager WebSocket (/api/v1/ws): pushes from vcam_server update the React Query cache directly,
 * so status badges, stats and events change without polling.
 *
 * Topics: camera.status, camera.state, camera.stats, event, fault, inspector, media.job
 */
import type { QueryClient } from "@tanstack/react-query"
import { useEffect, useSyncExternalStore } from "react"
import { wsUrl } from "@/api/client"
import { qk } from "@/api/queries"
import type { Camera, CameraStats, FarmStats } from "@/api/types"
import { useAuth } from "@/lib/auth/useAuth"

// ---------------------------------------------------------------- tiny external stores

function store<T>(initial: T) {
  let value = initial
  const subs = new Set<() => void>()
  return {
    get: () => value,
    set: (v: T) => {
      value = v
      subs.forEach((s) => s())
    },
    subscribe: (s: () => void) => {
      subs.add(s)
      return () => subs.delete(s)
    },
  }
}

export type WsState = "connecting" | "open" | "closed"
export interface LiveEvent {
  key: number
  camera_id: number
  topic: string
  utc_time: string
  operation: string
  origin: string
  data: Record<string, string>
  source: Record<string, string>
}
export interface StatsSample {
  t: number
  kbps: number
  cpu: number
  ram: number
  clients: number
}

const wsState = store<WsState>("closed")
const liveStats = store<{ farm: FarmStats | null; cameras: Record<string, CameraStats> }>({ farm: null, cameras: {} })
const statsHistory = store<StatsSample[]>([])
const liveEvents = store<LiveEvent[]>([])
let eventKey = 0
const MAX_EVENTS = 500
const MAX_SAMPLES = 300 // 10 min at one sample / 2 s

export const useWsState = () => useSyncExternalStore(wsState.subscribe, wsState.get)
export const useLiveStats = () => useSyncExternalStore(liveStats.subscribe, liveStats.get)
export const useStatsHistory = () => useSyncExternalStore(statsHistory.subscribe, statsHistory.get)
export const useLiveEvents = () => useSyncExternalStore(liveEvents.subscribe, liveEvents.get)
export const clearLiveEvents = () => liveEvents.set([])

// ---------------------------------------------------------------- message handling

type CameraList = { items: Camera[]; total: number }

function patchCamera(qc: QueryClient, id: number, patch: Partial<Camera>) {
  qc.setQueryData<CameraList>(qk.cameras, (old) => old && { ...old, items: old.items.map((c) => (c.id === id ? { ...c, ...patch } : c)) })
  qc.setQueryData<Camera>(qk.camera(id), (old) => old && { ...old, ...patch })
}

// Several messages about one camera often arrive together: refetch details once, shortly after.
const pending = new Map<number, ReturnType<typeof setTimeout>>()
function refreshCameraSoon(qc: QueryClient, id: number) {
  clearTimeout(pending.get(id))
  pending.set(
    id,
    setTimeout(() => {
      pending.delete(id)
      qc.invalidateQueries({ queryKey: qk.camera(id) })
      qc.invalidateQueries({ queryKey: qk.cameras })
    }, 800),
  )
}

function handle(qc: QueryClient, topic: string, data: Record<string, unknown>) {
  const id = Number(data.camera_id)
  switch (topic) {
    case "camera.status":
      patchCamera(qc, id, { status: String(data.status), last_error: (data.error as string | null) ?? null })
      refreshCameraSoon(qc, id)
      break
    case "camera.state":
      qc.invalidateQueries({ queryKey: qk.state(id) })
      refreshCameraSoon(qc, id)
      break
    case "camera.stats": {
      const farm = data.farm as FarmStats
      liveStats.set({ farm, cameras: (data.cameras as Record<string, CameraStats>) ?? {} })
      const h = statsHistory.get()
      const sample = { t: Date.now(), kbps: farm.kbps_out ?? 0, cpu: farm.cpu_percent ?? 0, ram: farm.ram_percent ?? 0, clients: farm.rtsp_clients ?? 0 }
      statsHistory.set(h.length >= MAX_SAMPLES ? [...h.slice(1), sample] : [...h, sample])
      break
    }
    case "event": {
      const ev = { ...(data as unknown as LiveEvent), key: ++eventKey }
      const list = liveEvents.get()
      liveEvents.set([ev, ...list.slice(0, MAX_EVENTS - 1)])
      qc.invalidateQueries({ queryKey: qk.eventState(id) })
      break
    }
    case "fault":
      refreshCameraSoon(qc, id)
      break
    case "media.job":
      qc.invalidateQueries({ queryKey: qk.jobs })
      break
    // "inspector": the Inspector page polls while "Follow" is on (cheaper than refetching per message)
  }
}

// ---------------------------------------------------------------- connection

function connect(qc: QueryClient): () => void {
  let ws: WebSocket | null = null
  let stopped = false
  let attempt = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  const open = () => {
    wsState.set("connecting")
    ws = new WebSocket(wsUrl())
    ws.onopen = () => {
      attempt = 0
      wsState.set("open")
      qc.invalidateQueries() // anything may have changed while we were disconnected
    }
    ws.onmessage = (msg) => {
      try {
        const { topic, data } = JSON.parse(msg.data as string)
        handle(qc, topic, data)
      } catch {
        // ignore malformed frames
      }
    }
    ws.onclose = () => {
      wsState.set("closed")
      if (stopped) return
      const delay = [1000, 2000, 5000, 10000][Math.min(attempt++, 3)]
      timer = setTimeout(open, delay)
    }
  }
  open()
  return () => {
    stopped = true
    clearTimeout(timer)
    ws?.close()
    wsState.set("closed")
  }
}

/** Mount once inside QueryClientProvider: keeps the WebSocket open while signed in. */
export function useRealtime(qc: QueryClient) {
  const { token } = useAuth()
  useEffect(() => (token ? connect(qc) : undefined), [qc, token])
}
