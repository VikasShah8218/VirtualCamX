import { Copy, Move3d, Pencil, Trash2 } from "lucide-react"
import { useState } from "react"
import { useCreateTemplate, useDeleteTemplate, useTemplates } from "@/api/queries"
import type { Template } from "@/api/types"
import { Field, PageHeader } from "@/components/common"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"

type StreamDef = [string, number, number, number, number] // codec, width, height, fps, kbps

/** Camera models. Built-ins are read-only; "Clone & edit" makes a custom one. */
export function TemplatesPage() {
  const templates = useTemplates()
  const del = useDeleteTemplate()
  const [editing, setEditing] = useState<Template | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  return (
    <>
      <PageHeader title="Templates" description="Camera models: identity, stream slots and capabilities used when creating cameras." />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {(templates.data ?? []).map((t) => (
          <div key={t.key} className="rounded-xl border bg-card p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2 font-medium">{t.name}{t.ptz && <Move3d className="size-4 text-primary" />}</div>
                <div className="font-mono text-xs text-muted-foreground">{t.key} · {t.model}</div>
              </div>
              <span className={t.builtin ? "rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground" : "rounded bg-primary/15 px-1.5 py-0.5 text-[10px] text-primary"}>{t.builtin ? "built-in" : "custom"}</span>
            </div>
            <div className="mt-3 space-y-1 text-xs">
              <div>Sensor <b>{t.native[0]}×{t.native[1]}</b></div>
              {(["main", "sub", "third"] as const).map((k) => t[k] && <div key={k} className="text-muted-foreground"><span className="inline-block w-10 capitalize">{k}</span> {String(t[k]![0])} {String(t[k]![1])}×{String(t[k]![2])} @{String(t[k]![3])}fps {String(t[k]![4])}kbps</div>)}
              <div className="text-muted-foreground">I/O: {t.inputs} in / {t.relays} relay</div>
            </div>
            <div className="mt-3 flex gap-1.5">
              <Button size="xs" variant="outline" onClick={() => setEditing({ ...t, key: t.builtin ? `${t.key}_custom` : t.key, name: t.builtin ? `${t.name} (custom)` : t.name, builtin: false })}>
                {t.builtin ? <><Copy /> Clone & edit</> : <><Pencil /> Edit</>}
              </Button>
              {!t.builtin && <Button size="xs" variant="ghost" onClick={() => setDeleting(t.key)}><Trash2 /> Delete</Button>}
            </div>
          </div>
        ))}
      </div>
      {editing && <TemplateDialog key={editing.key} initial={editing} existing={(templates.data ?? []).some((t) => t.key === editing.key && !t.builtin)} onClose={() => setEditing(null)} />}
      <ConfirmDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)} title="Delete template?" description="Existing cameras keep working; only new cameras can no longer use it." onConfirm={() => deleting && del.mutate(deleting)} />
    </>
  )
}

function TemplateDialog({ initial, existing, onClose }: { initial: Template; existing: boolean; onClose: () => void }) {
  const create = useCreateTemplate()
  const del = useDeleteTemplate()
  const [t, setT] = useState(initial)
  const stream = (k: "main" | "sub" | "third") => (t[k] as StreamDef | null | undefined) ?? null
  const setStream = (k: "main" | "sub" | "third", i: number, v: string | number) => {
    const cur = [...(stream(k) ?? ["H264", 640, 360, 10, 384])] as StreamDef
    cur[i] = v as never
    setT({ ...t, [k]: cur })
  }

  const save = async () => {
    const { key, builtin: _b, ...definition } = t
    void _b
    if (existing) await del.mutateAsync(key)
    create.mutate({ key, definition: definition as unknown as Record<string, unknown> }, { onSuccess: onClose })
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{existing ? "Edit template" : "New template"}</DialogTitle>
          <DialogDescription>Used for new cameras. Existing cameras are not changed.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Key (letters, digits, _)"><Input value={t.key} disabled={existing} onChange={(e) => setT({ ...t, key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })} /></Field>
          <Field label="Name"><Input value={t.name} onChange={(e) => setT({ ...t, name: e.target.value })} /></Field>
          <Field label="Model string (ONVIF)"><Input value={t.model} onChange={(e) => setT({ ...t, model: e.target.value })} /></Field>
          <Field label="Sensor resolution">
            <div className="flex gap-1.5">
              <Input type="number" value={t.native[0]} onChange={(e) => setT({ ...t, native: [Number(e.target.value), t.native[1]] })} />
              <Input type="number" value={t.native[1]} onChange={(e) => setT({ ...t, native: [t.native[0], Number(e.target.value)] })} />
            </div>
          </Field>
          <Field label="Main stream resolutions (WxH, comma separated)" className="col-span-2">
            <Input className="font-mono text-xs" value={t.main_res.map(([w, h]) => `${w}x${h}`).join(", ")} onChange={(e) => setT({ ...t, main_res: e.target.value.split(",").map((s) => s.trim().split("x").map(Number)).filter((r) => r.length === 2 && r.every((n) => n > 0)) })} />
          </Field>
        </div>
        {(["main", "sub", "third"] as const).map((k) => {
          const s = stream(k)
          return (
            <div key={k} className="rounded-lg border p-3">
              <div className="mb-2 flex items-center justify-between text-sm font-medium capitalize">
                {k} stream
                {k !== "main" && <label className="flex items-center gap-2 text-xs font-normal"><Switch size="sm" checked={!!s} onCheckedChange={(v) => setT({ ...t, [k]: v ? ["H264", 640, 360, 10, 384] : null })} /> enabled</label>}
              </div>
              {s && (
                <div className="grid grid-cols-5 gap-2">
                  <Select value={String(s[0])} onValueChange={(v) => setStream(k, 0, v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{["H264", "H265", "JPEG"].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                  </Select>
                  {(["width", "height", "fps", "kbps"] as const).map((lbl, i) => (
                    <Input key={lbl} type="number" title={lbl} placeholder={lbl} value={Number(s[i + 1])} onChange={(e) => setStream(k, i + 1, Number(e.target.value))} />
                  ))}
                </div>
              )}
            </div>
          )
        })}
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2"><Switch checked={t.ptz} onCheckedChange={(v) => setT({ ...t, ptz: v })} /> PTZ</label>
          <label className="flex items-center gap-2">Inputs <Input type="number" min={0} max={8} className="w-16" value={t.inputs} onChange={(e) => setT({ ...t, inputs: Number(e.target.value) })} /></label>
          <label className="flex items-center gap-2">Relays <Input type="number" min={0} max={8} className="w-16" value={t.relays} onChange={(e) => setT({ ...t, relays: Number(e.target.value) })} /></label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!t.key || !t.name || create.isPending} onClick={save}>Save template</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
