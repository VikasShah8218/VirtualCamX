import { Plus, Trash2 } from "lucide-react"
import { useCameraState, usePutSection } from "@/api/queries"
import type { Camera, OsdItem } from "@/api/types"
import { ErrorState, Field, Loading, Section } from "@/components/common"
import { SaveBar } from "@/components/SaveBar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useDraft } from "@/lib/useDraft"
import { cn } from "@/lib/utils"

const POSITIONS = ["UpperLeft", "UpperRight", "LowerLeft", "LowerRight"] as const

export function OsdTab({ camera: c }: { camera: Camera }) {
  const state = useCameraState(c.id)
  const saveOsd = usePutSection(c.id, "osd", "OSD saved")
  const saveEvents = usePutSection(c.id, "osd_show_events", "Saved")
  const { draft, setDraft, dirty, reset, saved } = useDraft(state.data?.osd)

  if (state.isLoading || !draft) return <Loading />
  if (state.isError) return <ErrorState error={state.error} />
  const max = state.data!.capabilities.max_osd

  const update = (token: string, patch: Partial<OsdItem>) => setDraft((l) => l.map((o) => (o.token === token ? { ...o, ...patch } : o)))
  const add = () => {
    let n = 1
    while (draft.some((o) => o.token === `OSD_${n}`)) n++
    setDraft((l) => [...l, { token: `OSD_${n}`, kind: "Plain", plain_text: "Text", position: "LowerLeft", x: -1, y: 1, font_size: 32, date_format: "yyyy-MM-dd", time_format: "HH:mm:ss", enabled: true }])
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <Section title="On-screen text" description="Burned into the video (Encode mode). Also readable/changeable by NVRs over ONVIF Media2 OSD calls."
        actions={<Button size="xs" variant="outline" disabled={draft.length >= max} onClick={add}><Plus /> Add text</Button>}>
        <div className="space-y-3">
          {draft.map((o) => (
            <div key={o.token} className="grid gap-3 rounded-lg border p-3 sm:grid-cols-[110px_1fr_140px_80px_auto]">
              <Field label="Type">
                <Select value={o.kind} onValueChange={(v) => update(o.token, { kind: v as OsdItem["kind"] })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Plain">Text</SelectItem>
                    <SelectItem value="DateAndTime">Date & time</SelectItem>
                    <SelectItem value="Date">Date</SelectItem>
                    <SelectItem value="Time">Time</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              {o.kind === "Plain" ? (
                <Field label="Text"><Input value={o.plain_text} onChange={(e) => update(o.token, { plain_text: e.target.value })} /></Field>
              ) : (
                <Field label="Format">
                  <div className="flex gap-2">
                    {o.kind !== "Time" && (
                      <Select value={o.date_format} onValueChange={(v) => update(o.token, { date_format: v })}>
                        <SelectTrigger className="flex-1"><SelectValue /></SelectTrigger>
                        <SelectContent>{["yyyy-MM-dd", "dd/MM/yyyy", "MM/dd/yyyy", "yyyy/MM/dd"].map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent>
                      </Select>
                    )}
                    {o.kind !== "Date" && (
                      <Select value={o.time_format} onValueChange={(v) => update(o.token, { time_format: v })}>
                        <SelectTrigger className="flex-1"><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="HH:mm:ss">24 h</SelectItem><SelectItem value="hh:mm:ss tt">12 h</SelectItem></SelectContent>
                      </Select>
                    )}
                  </div>
                </Field>
              )}
              <Field label="Position">
                <Select value={o.position === "Custom" ? "UpperLeft" : o.position} onValueChange={(v) => update(o.token, { position: v as OsdItem["position"] })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{POSITIONS.map((p) => <SelectItem key={p} value={p}>{p.replace(/([a-z])([A-Z])/, "$1 $2")}</SelectItem>)}</SelectContent>
                </Select>
              </Field>
              <Field label="Size"><Input type="number" min={12} max={96} value={o.font_size} onChange={(e) => update(o.token, { font_size: Number(e.target.value) || 32 })} /></Field>
              <div className="flex items-end gap-1 pb-1">
                <Switch checked={o.enabled} onCheckedChange={(v) => update(o.token, { enabled: v })} aria-label="Enabled" />
                <Button variant="ghost" size="icon-sm" aria-label="Remove" onClick={() => setDraft((l) => l.filter((x) => x.token !== o.token))}><Trash2 /></Button>
              </div>
            </div>
          ))}
        </div>
        <SaveBar dirty={dirty} saving={saveOsd.isPending} onReset={reset} onSave={() => saveOsd.mutate(draft, { onSuccess: saved })} note="Position changes restart the stream; text changes do not." />
      </Section>

      <div className="space-y-4">
        <Section title="Preview">
          <div className="relative aspect-video overflow-hidden rounded-md bg-video text-[10px] text-foreground">
            {draft.filter((o) => o.enabled).map((o) => (
              <span key={o.token} className={cn("absolute rounded bg-background/50 px-1",
                o.position === "UpperLeft" && "top-1.5 left-1.5", o.position === "UpperRight" && "top-1.5 right-1.5",
                o.position === "LowerLeft" && "bottom-1.5 left-1.5", (o.position === "LowerRight" || o.position === "Custom") && "right-1.5 bottom-1.5")}>
                {o.kind === "Plain" ? o.plain_text : o.kind === "Time" ? "12:34:56" : o.kind === "Date" ? o.date_format : `${o.date_format} 12:34:56`}
              </span>
            ))}
            {state.data!.osd_show_events && <span className="absolute top-6 right-1.5 font-bold text-danger">MOTION</span>}
          </div>
        </Section>
        <Section title="Event alerts on video">
          <label className="flex items-center justify-between gap-3 text-sm">
            <span>Show MOTION / TAMPER / ALARM IN text while events are active</span>
            <Switch checked={state.data!.osd_show_events} onCheckedChange={(v) => saveEvents.mutate(v)} />
          </label>
        </Section>
      </div>
    </div>
  )
}
