import { ChevronLeft, ChevronRight, Maximize2, Minimize2, Pause, Play, Repeat } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router"
import { managerWhepUrl, snapshotUrl } from "@/api/client"
import { useCameras } from "@/api/queries"
import type { Camera } from "@/api/types"
import { EmptyState, PageHeader } from "@/components/common"
import { LivePlayer } from "@/components/LivePlayer"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { getToken } from "@/lib/auth/session"
import { eventActive } from "@/lib/format"
import { useLiveEvents } from "@/lib/realtime"
import { readStored, writeStored } from "@/lib/storage"
import { useInterval } from "@/lib/useInterval"
import { cn } from "@/lib/utils"

const KEY = "vcamx.livewall"
const LAYOUTS = [1, 4, 9, 16] as const

/** Grid of live tiles. Uses the H.264 sub stream; at most 16 WebRTC sessions (LivePlayer enforces it). */
export function LiveWallPage() {
  const cameras = useCameras()
  const [prefs, setPrefs] = useState(() => readStored(KEY, { layout: 9 as number, cycle: 0 }))
  const [page, setPage] = useState(0)
  const [single, setSingle] = useState<Camera | null>(null)
  const [paused, setPaused] = useState(false)
  const running = useMemo(() => (cameras.data ?? []).filter((c) => c.status === "running"), [cameras.data])
  const pages = Math.max(1, Math.ceil(running.length / prefs.layout))
  const tiles = running.slice(page * prefs.layout, page * prefs.layout + prefs.layout)
  const save = (p: Partial<typeof prefs>) => setPrefs((old) => { const n = { ...old, ...p }; writeStored(KEY, n); return n })

  useEffect(() => { if (page >= pages) setPage(0) }, [page, pages])
  useInterval(() => setPage((p) => (p + 1) % pages), prefs.cycle && !paused && pages > 1 && !single ? prefs.cycle * 1000 : null)

  const cols = { 1: "grid-cols-1", 4: "grid-cols-2", 9: "grid-cols-3", 16: "grid-cols-4" }[prefs.layout] ?? "grid-cols-3"

  return (
    <>
      <PageHeader
        title="Live Wall"
        description={`${running.length} running camera(s) · sub streams over WebRTC`}
        actions={
          <>
            <ToggleGroup type="single" variant="outline" value={String(prefs.layout)} onValueChange={(v) => v && (save({ layout: Number(v) }), setPage(0))}>
              {LAYOUTS.map((l) => <ToggleGroupItem key={l} value={String(l)} className="px-3 text-xs">{l}</ToggleGroupItem>)}
            </ToggleGroup>
            <Select value={String(prefs.cycle)} onValueChange={(v) => save({ cycle: Number(v) })}>
              <SelectTrigger className="w-36"><Repeat className="size-4" /><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="0">No auto-cycle</SelectItem>
                {[10, 20, 30, 60].map((s) => <SelectItem key={s} value={String(s)}>Cycle {s}s</SelectItem>)}
              </SelectContent>
            </Select>
            {prefs.cycle > 0 && <Button variant="ghost" size="icon" onClick={() => setPaused((p) => !p)} aria-label="Pause cycle">{paused ? <Play /> : <Pause />}</Button>}
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" disabled={pages < 2} onClick={() => setPage((p) => (p - 1 + pages) % pages)} aria-label="Previous page"><ChevronLeft /></Button>
              <span className="w-14 text-center text-sm tabular-nums">{page + 1} / {pages}</span>
              <Button variant="ghost" size="icon" disabled={pages < 2} onClick={() => setPage((p) => (p + 1) % pages)} aria-label="Next page"><ChevronRight /></Button>
            </div>
          </>
        }
      />
      {cameras.isSuccess && running.length === 0 && (
        <EmptyState title="No running cameras" action={<Button asChild><Link to="/cameras">Go to cameras</Link></Button>}>Start a camera to see it here.</EmptyState>
      )}
      {single ? (
        <div className="space-y-2">
          <Button variant="outline" size="sm" onClick={() => setSingle(null)}><Minimize2 /> Back to grid</Button>
          <Tile c={single} big onToggle={() => setSingle(null)} />
        </div>
      ) : (
        <div className={cn("grid gap-2", cols)}>
          {tiles.map((c) => <Tile key={c.id} c={c} onToggle={() => setSingle(c)} />)}
        </div>
      )}
    </>
  )
}

function Tile({ c, big, onToggle }: { c: Camera; big?: boolean; onToggle: () => void }) {
  const events = useLiveEvents()
  const [now, setNow] = useState(() => Date.now())
  useInterval(() => setNow(Date.now()), 1000)
  // Red border while this camera has an active alarm in the last events
  const alarm = events.some((e) => e.camera_id === c.id && eventActive(e.data) && now - new Date(e.utc_time).getTime() < 15_000)
  const stream = big ? (c.streams.find((s) => s.encoding === "H264")?.key ?? "main") : (c.streams.find((s) => s.key !== "main" && s.encoding === "H264")?.key ?? c.streams.find((s) => s.encoding === "H264")?.key ?? "sub")
  return (
    <div className={cn("group relative overflow-hidden rounded-lg border-2 border-transparent", alarm && "border-danger")} onDoubleClick={onToggle}>
      <LivePlayer
        whepUrl={managerWhepUrl(c.id, stream)}
        headers={{ Authorization: `Bearer ${getToken() ?? ""}` }}
        snapshotUrl={(b) => snapshotUrl(c.id, b)}
        className={cn("w-full", big ? "aspect-video max-h-[75vh]" : "aspect-video")}
        overlay={big}
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center gap-2 bg-gradient-to-b from-background/80 to-transparent px-2 py-1.5 text-xs">
        <StatusBadge status={c.status} compact />
        <span className="truncate font-medium">{c.name}</span>
        {alarm && <span className="ml-auto rounded bg-danger px-1.5 text-[10px] font-bold text-background">ALARM</span>}
      </div>
      <div className="absolute right-1.5 bottom-1.5 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <Button size="icon-xs" variant="secondary" asChild><Link to={`/cameras/${c.id}`} aria-label="Open camera">↗</Link></Button>
        <Button size="icon-xs" variant="secondary" onClick={onToggle} aria-label="Toggle single view">{big ? <Minimize2 /> : <Maximize2 />}</Button>
      </div>
    </div>
  )
}
