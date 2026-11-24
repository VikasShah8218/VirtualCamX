import { Film, Play, RefreshCw, RotateCcw, ShieldAlert, Square, Trash2, X, Zap } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { useBulkAction, useBulkFault, useBulkSource, useBulkTrigger, useFaultTypes } from "@/api/queries"
import type { BulkAction, SourceSpec } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { SourcePicker, StreamModePicker } from "@/components/SourcePicker"
import { Field } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { makeSource } from "@/lib/source"

/** Shown when cameras are selected in the list: one action for all of them. */
export function BulkActionBar({ ids, onClear }: { ids: number[]; onClear: () => void }) {
  const bulk = useBulkAction()
  const trigger = useBulkTrigger()
  const fault = useBulkFault()
  const faultTypes = useFaultTypes()
  const [confirm, setConfirm] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const n = ids.length
  if (!n) return null

  const run = (action: BulkAction) => bulk.mutate({ ids, action }, { onSuccess: (r) => {
    const failed = Object.entries(r.results).filter(([, v]) => v !== "ok")
    if (failed.length) toast.warning(`${failed.length} of ${n} failed`, { description: failed.slice(0, 3).map(([k, v]) => `#${k}: ${v}`).join("\n") })
    if (action === "delete") onClear()
  } })

  return (
    <div className="sticky bottom-2 z-20 mx-auto mt-3 flex w-fit max-w-full flex-wrap items-center gap-1.5 rounded-xl border bg-popover px-3 py-2 shadow-lg">
      <span className="mr-1 text-sm font-medium">{n} selected</span>
      <Button size="sm" variant="ghost" onClick={() => run("start")}><Play /> Start</Button>
      <Button size="sm" variant="ghost" onClick={() => run("stop")}><Square /> Stop</Button>
      <Button size="sm" variant="ghost" onClick={() => run("restart")}><RefreshCw /> Restart</Button>
      <Button size="sm" variant="ghost" onClick={() => run("reboot")}><RotateCcw /> Reboot</Button>
      <Button size="sm" variant="ghost" onClick={() => setSourceOpen(true)}><Film /> Source</Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild><Button size="sm" variant="ghost"><Zap /> Event</Button></DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Pulse for 10 s</DropdownMenuLabel>
          {(["motion", "tamper", "video_loss", "digital_input"] as const).map((k) => (
            <DropdownMenuItem key={k} onSelect={() => trigger.mutate({ ids, kind: k, duration_s: 10, state: null, token: null })} className="capitalize">
              {k.replace("_", " ")}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <DropdownMenu>
        <DropdownMenuTrigger asChild><Button size="sm" variant="ghost"><ShieldAlert /> Fault</Button></DropdownMenuTrigger>
        <DropdownMenuContent className="w-60">
          <DropdownMenuLabel>Apply for 60 s (default parameters)</DropdownMenuLabel>
          {Object.entries(faultTypes.data ?? {}).map(([k, t]) => (
            <DropdownMenuItem key={k} onSelect={() => fault.mutate({ ids, type: k, params: t.params, duration_s: 60 })}>
              {t.label}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem disabled>More options on the Faults page</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Button size="sm" variant="destructive" onClick={() => setConfirm(true)}><Trash2 /> Delete</Button>
      <Button size="icon-sm" variant="ghost" onClick={onClear} aria-label="Clear selection"><X /></Button>

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={`Delete ${n} camera${n > 1 ? "s" : ""}?`}
        description="They disappear from the network. NVRs using them will lose them."
        typeToConfirm={n > 10 ? String(n) : undefined}
        confirmLabel={`Delete ${n}`}
        onConfirm={() => run("delete")}
      />
      <BulkSourceDialog open={sourceOpen} onOpenChange={setSourceOpen} ids={ids} />
    </div>
  )
}

function BulkSourceDialog({ open, onOpenChange, ids }: { open: boolean; onOpenChange: (o: boolean) => void; ids: number[] }) {
  const setSource = useBulkSource()
  const [source, setSrc] = useState<SourceSpec>(makeSource({ type: "file" }))
  const [mode, setMode] = useState<"encode" | "passthrough">("passthrough")
  const [offsetStep, setOffsetStep] = useState(0.5)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Change source of {ids.length} camera(s)</DialogTitle>
          <DialogDescription>Live switch: NVRs see a short RTSP reconnect.</DialogDescription>
        </DialogHeader>
        <SourcePicker value={source} onChange={setSrc} showOffset={false} />
        {source.type === "file" && (
          <>
            <Field label="Start offset step (seconds)"><Input type="number" min={0} step={0.5} className="w-32" value={offsetStep} onChange={(e) => setOffsetStep(Number(e.target.value) || 0)} /></Field>
            <StreamModePicker value={mode} onChange={setMode} />
          </>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            disabled={setSource.isPending || ((source.type === "file" || source.type === "image") && !source.path)}
            onClick={() =>
              setSource.mutate(
                { ids, source, offset_step_s: source.type === "file" ? offsetStep : 0, stream_mode: source.type === "file" ? mode : "encode", spread_paths: null },
                { onSuccess: () => onOpenChange(false) },
              )
            }
          >
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
