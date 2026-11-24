import { Link } from "react-router"
import { useCameras } from "@/api/queries"
import { eventActive, fmtTime, topicLabel } from "@/lib/format"
import { useLiveEvents, type LiveEvent } from "@/lib/realtime"
import { cn } from "@/lib/utils"

/** Events pushed over the WebSocket since this tab opened (newest first). */
export function EventFeed({ limit = 50, cameraId, compact, filter }: {
  limit?: number
  cameraId?: number
  compact?: boolean
  filter?: (e: LiveEvent) => boolean
}) {
  const events = useLiveEvents()
  const cameras = useCameras()
  const names = new Map((cameras.data ?? []).map((c) => [c.id, c.name]))
  const list = events.filter((e) => (cameraId == null || e.camera_id === cameraId) && (!filter || filter(e))).slice(0, limit)

  if (list.length === 0) {
    return <div className="py-6 text-center text-sm text-muted-foreground">No events yet. Trigger one from the Event Simulator or a camera page.</div>
  }
  return (
    <div className="divide-y text-sm">
      {list.map((e) => {
        const on = eventActive(e.data)
        return (
          <div key={e.key} className={cn("flex items-center gap-2", compact ? "py-1.5" : "py-2")}>
            <span className="w-16 shrink-0 font-mono text-[11px] text-muted-foreground tabular-nums">{fmtTime(e.utc_time)}</span>
            <span className={cn("size-2 shrink-0 rounded-full", on ? "bg-warning" : "bg-muted-foreground/40")} />
            {cameraId == null && (
              <Link to={`/cameras/${e.camera_id}`} className="w-28 shrink-0 truncate font-medium hover:underline">
                {names.get(e.camera_id) ?? `#${e.camera_id}`}
              </Link>
            )}
            <span className="min-w-0 flex-1 truncate">
              {topicLabel(e.topic)} <span className={on ? "text-warning" : "text-muted-foreground"}>{on ? "on" : "off"}</span>
              {Object.values(e.source).find((v) => /Input|Relay/.test(v)) ? <span className="text-muted-foreground"> · {Object.values(e.source)[0]}</span> : null}
            </span>
            {!compact && <span className="shrink-0 text-xs text-muted-foreground">{e.origin}</span>}
          </div>
        )
      })}
    </div>
  )
}
