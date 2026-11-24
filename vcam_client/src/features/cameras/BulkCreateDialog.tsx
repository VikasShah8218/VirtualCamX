import { FolderOpen, Loader2 } from "lucide-react"
import { useMemo, useState } from "react"
import { useBulkCreate, useCameras, useTemplates } from "@/api/queries"
import type { SourceSpec } from "@/api/types"
import { Field } from "@/components/common"
import { PathPickerDialog } from "@/components/PathPickerDialog"
import { SourcePicker, StreamModePicker } from "@/components/SourcePicker"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { fmtKbps, renderNamePattern } from "@/lib/format"
import { baseName, makeSource } from "@/lib/source"
import { cn } from "@/lib/utils"
import { TemplatePicker } from "./TemplatePicker"

type Footage = "one" | "spread" | "pattern"

/** 3 steps: how many & names -> model & footage -> review (CPU / bandwidth estimate) -> create. */
export function BulkCreateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const bulk = useBulkCreate()
  const cameras = useCameras()
  const templates = useTemplates()
  const [step, setStep] = useState(1)
  const [count, setCount] = useState(20)
  const [pattern, setPattern] = useState("Lab-{n:03d}")
  const [startPort, setStartPort] = useState("")
  const [template, setTemplate] = useState("bullet_2mp")
  const [footage, setFootage] = useState<Footage>("pattern")
  const [source, setSource] = useState<SourceSpec>(makeSource({ type: "file" }))
  const [folderFiles, setFolderFiles] = useState<string[]>([])
  const [folder, setFolder] = useState<string | null>(null)
  const [picker, setPicker] = useState(false)
  const [offsetStep, setOffsetStep] = useState(0.5)
  const [mode, setMode] = useState<"encode" | "passthrough">("passthrough")

  const nextNumber = Math.max(0, ...(cameras.data ?? []).map((c) => c.number)) + 1
  const names = useMemo(() => Array.from({ length: Math.min(count, 1000) }, (_, i) => renderNamePattern(pattern, nextNumber + i)), [count, pattern, nextNumber])
  const tpl = templates.data?.find((t) => t.key === template)
  const effectiveMode = footage === "pattern" ? "encode" : mode
  const kbpsPerCam = tpl ? Number(tpl.main[4] ?? 0) + Number(tpl.sub?.[4] ?? 0) + Number(tpl.third?.[4] ?? 0) : 0
  const cpu = count * (effectiveMode === "encode" ? 1.2 : 0.05)
  const valid = count >= 1 && count <= 1000 && (footage === "pattern" || (footage === "one" ? !!source.path : folderFiles.length > 0))

  const reset = () => { setStep(1); bulk.reset() }

  const submit = () =>
    bulk.mutate(
      {
        count,
        template_key: template,
        name_pattern: pattern,
        first_index: null,
        start_port: startPort ? Number(startPort) : null,
        stream_mode: effectiveMode,
        source: footage === "one" ? source : footage === "pattern" ? makeSource({ type: "test_pattern" }) : null,
        spread_paths: footage === "spread" ? folderFiles : null,
        offset_step_s: footage === "pattern" ? 0 : offsetStep,
        username: null,
        password: null,
      },
      { onSuccess: () => { onOpenChange(false); reset() } },
    )

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) reset() }}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Bulk create cameras</DialogTitle>
          <DialogDescription>Step {step} of 3 · {["How many & names", "Model & footage", "Review"][step - 1]}</DialogDescription>
        </DialogHeader>
        <div className="flex gap-1">{[1, 2, 3].map((s) => <div key={s} className={cn("h-1 flex-1 rounded-full", s <= step ? "bg-primary" : "bg-muted")} />)}</div>

        {step === 1 && (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="How many cameras"><Input type="number" min={1} max={1000} value={count} onChange={(e) => setCount(Math.max(1, Math.min(1000, Number(e.target.value) || 1)))} /></Field>
              <Field label="Name pattern" hint="{n:03d} = 001, 002…" className="sm:col-span-2"><Input value={pattern} onChange={(e) => setPattern(e.target.value)} /></Field>
            </div>
            <Field label="First HTTP/ONVIF port" hint="Empty = next free ports"><Input type="number" className="w-40" value={startPort} onChange={(e) => setStartPort(e.target.value)} /></Field>
            <div className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
              Preview: <span className="font-mono text-foreground">{names.slice(0, 3).join(", ")}{count > 3 ? ` … ${names[names.length - 1]}` : ""}</span>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <Field label="Camera model"><TemplatePicker value={template} onChange={setTemplate} /></Field>
            <Field label="Footage">
              <ToggleGroup type="single" variant="outline" value={footage} onValueChange={(v) => v && setFootage(v as Footage)}>
                <ToggleGroupItem value="pattern" className="px-3 text-xs">Test pattern</ToggleGroupItem>
                <ToggleGroupItem value="one" className="px-3 text-xs">One file for all</ToggleGroupItem>
                <ToggleGroupItem value="spread" className="px-3 text-xs">Spread files from a folder</ToggleGroupItem>
              </ToggleGroup>
            </Field>
            {footage === "one" && <SourcePicker value={source} onChange={(s) => setSource({ ...s, type: "file" })} showOffset={false} />}
            {footage === "spread" && (
              <div className="space-y-2">
                <Button variant="secondary" onClick={() => setPicker(true)}><FolderOpen /> {folder ? "Change folder" : "Choose folder…"}</Button>
                {folder && (
                  <div className="rounded-md border p-2 text-xs">
                    <div className="mb-1 font-mono text-muted-foreground">{folder}</div>
                    <div className="max-h-28 overflow-y-auto">
                      {names.slice(0, 8).map((n, i) => (
                        <div key={n} className="flex gap-2"><span className="w-24 shrink-0 font-mono">{n}</span><span className="truncate text-muted-foreground">{baseName(folderFiles[i % folderFiles.length])}</span></div>
                      ))}
                      {count > 8 && <div className="text-muted-foreground">… round-robin over {folderFiles.length} files</div>}
                    </div>
                  </div>
                )}
                <PathPickerDialog open={picker} onOpenChange={setPicker} mode="folder" onPick={(p, files) => { setFolder(p); setFolderFiles(files ?? []) }} />
              </div>
            )}
            {footage !== "pattern" && (
              <>
                <Field label="Start offset step (seconds)" hint="Camera 1 starts at 0 s, camera 2 at this value, camera 3 at twice… so tiles don't look identical.">
                  <Input type="number" min={0} step={0.5} className="w-32" value={offsetStep} onChange={(e) => setOffsetStep(Number(e.target.value) || 0)} />
                </Field>
                <Field label="Stream mode"><StreamModePicker value={mode} onChange={setMode} /></Field>
              </>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-2 rounded-lg border p-3">
              <span className="text-muted-foreground">Cameras</span><span>{count} × {tpl?.name}</span>
              <span className="text-muted-foreground">Names</span><span className="truncate font-mono text-xs">{names[0]} … {names[names.length - 1]}</span>
              <span className="text-muted-foreground">Footage</span><span>{footage === "pattern" ? "Test pattern" : footage === "one" ? baseName(source.path) : `${folderFiles.length} files, round-robin`}</span>
              <span className="text-muted-foreground">Mode</span><span className="capitalize">{effectiveMode}</span>
              <span className="text-muted-foreground">Estimated CPU</span><span className={cpu > 8 ? "text-warning" : undefined}>≈ {cpu.toFixed(1)} cores</span>
              <span className="text-muted-foreground">Bandwidth if all are watched</span><span>{fmtKbps(kbpsPerCam * count)}</span>
            </div>
            {effectiveMode === "encode" && count > 8 && (
              <div className="rounded-md bg-warning/15 px-3 py-2 text-xs text-warning">Encode mode uses about 1.2 CPU cores per 1080p camera. For many cameras use footage + Passthrough.</div>
            )}
          </div>
        )}

        <DialogFooter>
          {step > 1 && <Button variant="ghost" onClick={() => setStep((s) => s - 1)}>Back</Button>}
          {step < 3 ? (
            <Button disabled={step === 2 && !valid} onClick={() => setStep((s) => s + 1)}>Next</Button>
          ) : (
            <Button disabled={!valid || bulk.isPending} onClick={submit}>
              {bulk.isPending && <Loader2 className="animate-spin" />} Create {count} cameras
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
