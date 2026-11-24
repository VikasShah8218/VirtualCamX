import { Eraser, Trash2, Zap } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router"
import { useBulkTrigger, useCameras, useDeleteSchedule, useSchedules, useUpdateSchedule } from "@/api/queries"
import type { TriggerIn } from "@/api/types"
import { Field, PageHeader, Section } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { clearLiveEvents } from "@/lib/realtime"
import { EventFeed } from "./EventFeed"

type Kind = TriggerIn["kind"]

export function EventsPage() {
  const cameras = useCameras()
  const trigger = useBulkTrigger()
  const schedules = useSchedules()
  const update = useUpdateSchedule()
  const del = useDeleteSchedule()
  const [kind, setKind] = useState<Kind>("motion")
  const [duration, setDuration] = useState(10)
  const [all, setAll] = useState(true)
  const [ids, setIds] = useState<Set<number>>(new Set())
  const [feedCamera, setFeedCamera] = useState("all")
  const running = useMemo(() => (cameras.data ?? []).filter((c) => c.status === "running"), [cameras.data])
  const names = new Map((cameras.data ?? []).map((c) => [c.id, c.name]))

  const fire = () => trigger.mutate({ ids: all ? null : [...ids], kind, duration_s: duration, state: null, token: null })

  return (
    <>
      <PageHeader title="Event simulator" description="Fire ONVIF events on many cameras at once (NVR event-load tests) and watch them arrive." />
      <div className="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Section title="Fire events">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Event">
                <Select value={kind} onValueChange={(v) => setKind(v as Kind)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="motion">Motion</SelectItem>
                    <SelectItem value="tamper">Tamper</SelectItem>
                    <SelectItem value="video_loss">Video loss</SelectItem>
                    <SelectItem value="digital_input">Digital input 1</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Pulse (seconds)"><Input type="number" min={1} value={duration} onChange={(e) => setDuration(Math.max(1, Number(e.target.value) || 1))} /></Field>
            </div>
            <label className="mt-3 flex items-center gap-2 text-sm"><Switch checked={all} onCheckedChange={setAll} /> All running cameras ({running.length})</label>
            {!all && (
              <div className="mt-2 max-h-56 space-y-1 overflow-y-auto rounded-md border p-2">
                {running.map((c) => (
                  <label key={c.id} className="flex items-center gap-2 text-sm">
                    <Checkbox checked={ids.has(c.id)} onCheckedChange={(v) => setIds((s) => { const n = new Set(s); if (v) n.add(c.id); else n.delete(c.id); return n })} />
                    {c.name}
                  </label>
                ))}
              </div>
            )}
            <Button className="mt-3 w-full" disabled={trigger.isPending || (!all && ids.size === 0)} onClick={fire}><Zap /> Fire on {all ? running.length : ids.size} camera(s)</Button>
          </Section>

          <Section title="All schedules" description="Create schedules on a camera's I/O & Events tab.">
            {(schedules.data ?? []).length === 0 && <div className="text-sm text-muted-foreground">No schedules.</div>}
            <div className="space-y-1.5">
              {(schedules.data ?? []).map((s) => (
                <div key={s.id} className="flex items-center gap-2 text-sm">
                  <Switch size="sm" checked={s.enabled} onCheckedChange={(v) => update.mutate({ ...s, enabled: v })} />
                  <Link className="w-28 truncate font-medium hover:underline" to={`/cameras/${s.camera_id}/events`}>{names.get(s.camera_id) ?? `#${s.camera_id}`}</Link>
                  <span className="capitalize">{s.kind.replace("_", " ")}</span>
                  <span className="flex-1 truncate text-xs text-muted-foreground">{s.mode === "random" ? `${s.interval_s}–${s.interval_max_s}s` : `every ${s.interval_s}s`} · {s.active_s}s on</span>
                  <Button variant="ghost" size="icon-xs" onClick={() => del.mutate(s.id)} aria-label="Delete"><Trash2 /></Button>
                </div>
              ))}
            </div>
          </Section>
        </div>

        <Section
          title="Live event feed"
          description="Events pushed by the server since this page opened"
          actions={
            <div className="flex gap-2">
              <Select value={feedCamera} onValueChange={setFeedCamera}>
                <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All cameras</SelectItem>
                  {(cameras.data ?? []).map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button size="icon" variant="ghost" onClick={clearLiveEvents} aria-label="Clear feed"><Eraser /></Button>
            </div>
          }
        >
          <div className="max-h-[70vh] overflow-y-auto">
            <EventFeed limit={300} cameraId={feedCamera === "all" ? undefined : Number(feedCamera)} />
          </div>
        </Section>
      </div>
    </>
  )
}
