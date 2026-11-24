import { Activity, Plus, Trash2, Zap } from "lucide-react"
import { useState } from "react"
import { useCameraState, useCreateSchedule, useDeleteSchedule, useEventState, useSchedules, useTriggerEvent, useUpdateSchedule } from "@/api/queries"
import type { Camera, TriggerIn } from "@/api/types"
import { Field, Section } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { EventFeed } from "@/features/events/EventFeed"
import { eventActive, topicLabel } from "@/lib/format"
import { cn } from "@/lib/utils"

type Kind = TriggerIn["kind"]
const KINDS: { kind: Kind; label: string }[] = [
  { kind: "motion", label: "Motion" },
  { kind: "tamper", label: "Tamper" },
  { kind: "video_loss", label: "Video loss" },
]

export function EventsTab({ camera: c }: { camera: Camera }) {
  const trigger = useTriggerEvent()
  const eventState = useEventState(c.id)
  const state = useCameraState(c.id)
  const [pulse, setPulse] = useState(10)
  const running = c.status === "running"
  const props = eventState.data ?? []
  const isOn = (topicPart: string, token?: string) =>
    props.some((p) => p.topic.includes(topicPart) && eventActive(p.data) && (!token || Object.values(p.source).includes(token)))

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Section title="Fire events" description="NVRs subscribed to this camera (PullPoint or push) receive them like real camera events.">
        <div className="mb-3 flex items-center gap-2 text-sm">
          Pulse length <Input type="number" min={1} className="w-20" value={pulse} onChange={(e) => setPulse(Math.max(1, Number(e.target.value) || 1))} /> s
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {KINDS.map(({ kind, label }) => {
            const on = isOn(kind === "motion" ? "MotionAlarm" : kind === "tamper" ? "GlobalSceneChange" : "SignalLoss")
            return (
              <div key={kind} className={cn("rounded-lg border p-3", on && "border-warning bg-warning/10")}>
                <div className="mb-2 flex items-center justify-between text-sm font-medium">{label}<span className={cn("size-2 rounded-full", on ? "animate-pulse bg-warning" : "bg-muted-foreground/30")} /></div>
                <div className="flex flex-wrap gap-1.5">
                  <Button size="xs" disabled={!running} onClick={() => trigger.mutate({ id: c.id, kind, duration_s: pulse, state: null, token: null })}><Zap /> Pulse</Button>
                  <Button size="xs" variant="outline" disabled={!running} onClick={() => trigger.mutate({ id: c.id, kind, state: !on, duration_s: 0, token: null })}>{on ? "Turn off" : "Hold on"}</Button>
                </div>
              </div>
            )
          })}
        </div>

        <h3 className="mt-5 mb-2 text-xs font-medium text-muted-foreground">Digital inputs (alarm in)</h3>
        {(state.data?.io.inputs ?? []).length === 0 && <div className="text-sm text-muted-foreground">This model has no digital inputs.</div>}
        <div className="flex flex-wrap gap-2">
          {(state.data?.io.inputs ?? []).map((di) => {
            const on = isOn("DigitalInput", di.token)
            return (
              <label key={di.token} className={cn("flex items-center gap-2 rounded-lg border px-3 py-2 text-sm", on && "border-warning bg-warning/10")}>
                <Switch checked={on} disabled={!running} onCheckedChange={(v) => trigger.mutate({ id: c.id, kind: "digital_input", state: v, token: di.token, duration_s: 0 })} />
                {di.token}
              </label>
            )
          })}
        </div>

        <h3 className="mt-5 mb-2 text-xs font-medium text-muted-foreground">Relay outputs (set by the NVR)</h3>
        {(state.data?.io.relays ?? []).length === 0 && <div className="text-sm text-muted-foreground">This model has no relay outputs.</div>}
        <div className="flex flex-wrap gap-2">
          {(state.data?.io.relays ?? []).map((r) => {
            const on = props.some((p) => p.topic.includes("Relay") && Object.values(p.source).includes(r.token) && eventActive(p.data))
            return (
              <div key={r.token} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm">
                <Activity className={cn("size-4", on ? "text-warning" : "text-muted-foreground")} />
                {r.token} <span className={on ? "text-warning" : "text-muted-foreground"}>{on ? "active" : "inactive"}</span>
                <span className="text-xs text-muted-foreground">({r.mode})</span>
              </div>
            )
          })}
        </div>
      </Section>

      <div className="space-y-4">
        <Schedules cameraId={c.id} inputs={(state.data?.io.inputs ?? []).map((i) => i.token)} />
        <Section title="Current event state" description="What a new subscriber receives first (ONVIF 'Initialized' messages)">
          <div className="grid gap-1 text-sm sm:grid-cols-2">
            {props.map((p, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className={cn("size-2 rounded-full", eventActive(p.data) ? "bg-warning" : "bg-muted-foreground/30")} />
                {topicLabel(p.topic)}
                <span className="truncate text-xs text-muted-foreground">{String(Object.values(p.source).find((v) => /Input|Relay/.test(String(v))) ?? "")}</span>
              </div>
            ))}
          </div>
        </Section>
        <Section title="Live events (this tab)"><EventFeed cameraId={c.id} limit={20} /></Section>
      </div>
    </div>
  )
}

function Schedules({ cameraId, inputs }: { cameraId: number; inputs: string[] }) {
  const schedules = useSchedules(cameraId)
  const create = useCreateSchedule()
  const update = useUpdateSchedule()
  const del = useDeleteSchedule()
  const [kind, setKind] = useState<Kind>("motion")
  const [mode, setMode] = useState<"periodic" | "random">("periodic")
  const [every, setEvery] = useState(60)
  const [intervalMax, setIntervalMax] = useState(120)
  const [active, setActive] = useState(10)

  return (
    <Section title="Schedules" description="Automatic events for soak tests">
      <div className="mb-3 space-y-1.5">
        {(schedules.data ?? []).length === 0 && <div className="text-sm text-muted-foreground">No schedules.</div>}
        {(schedules.data ?? []).map((s) => (
          <div key={s.id} className="flex items-center gap-2 text-sm">
            <Switch size="sm" checked={s.enabled} onCheckedChange={(v) => update.mutate({ ...s, enabled: v })} />
            <span className="capitalize">{s.kind.replace("_", " ")}{s.token ? ` (${s.token})` : ""}</span>
            <span className="flex-1 text-xs text-muted-foreground">
              {s.mode === "random" ? `random every ${s.interval_s}–${s.interval_max_s}s` : `every ${s.interval_s}s`}, on for {s.active_s}s
            </span>
            <Button variant="ghost" size="icon-xs" onClick={() => del.mutate(s.id)} aria-label="Delete"><Trash2 /></Button>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <Field label="Event">
          <Select value={kind} onValueChange={(v) => setKind(v as Kind)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="motion">Motion</SelectItem>
              <SelectItem value="tamper">Tamper</SelectItem>
              <SelectItem value="video_loss">Video loss</SelectItem>
              {inputs.length > 0 && <SelectItem value="digital_input">Digital input</SelectItem>}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Timing">
          <Select value={mode} onValueChange={(v) => setMode(v as "periodic" | "random")}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="periodic">Every N s</SelectItem><SelectItem value="random">Random</SelectItem></SelectContent>
          </Select>
        </Field>
        <Field label={mode === "random" ? "Min s" : "Every s"}><Input type="number" min={1} value={every} onChange={(e) => setEvery(Number(e.target.value) || 1)} /></Field>
        {mode === "random" && <Field label="Max s"><Input type="number" min={1} value={intervalMax} onChange={(e) => setIntervalMax(Number(e.target.value) || 1)} /></Field>}
        <Field label="On for s"><Input type="number" min={1} value={active} onChange={(e) => setActive(Number(e.target.value) || 1)} /></Field>
      </div>
      <Button size="sm" className="mt-3" disabled={create.isPending} onClick={() => create.mutate({ camera_id: cameraId, kind, token: kind === "digital_input" ? inputs[0] : null, mode, interval_s: every, interval_max_s: Math.max(every, intervalMax), active_s: active, enabled: true })}>
        <Plus /> Add schedule
      </Button>
    </Section>
  )
}
