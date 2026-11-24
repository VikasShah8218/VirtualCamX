import { AlertCircle, CheckCircle2, FolderOpen, Loader2 } from "lucide-react"
import { useEffect, useState } from "react"
import { useProbe } from "@/api/queries"
import type { SourceSpec } from "@/api/types"
import { Field } from "@/components/common"
import { PathPickerDialog } from "@/components/PathPickerDialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { fmtDuration, fmtRes } from "@/lib/format"
import { makeSource } from "@/lib/source"

const TYPES: { id: SourceSpec["type"]; label: string }[] = [
  { id: "test_pattern", label: "Test pattern" },
  { id: "file", label: "Video file" },
  { id: "image", label: "Image" },
  { id: "rtsp", label: "RTSP relay" },
]

/** What the camera "sees": test pattern, a video file by path (probed right away), an image or an RTSP relay. */
export function SourcePicker({ value, onChange, showOffset = true }: { value: SourceSpec; onChange: (s: SourceSpec) => void; showOffset?: boolean }) {
  const [picker, setPicker] = useState(false)
  const probe = useProbe()
  const { mutate: runProbe, reset: resetProbe } = probe

  // Probe the chosen file so the user sees codec/resolution or a clear error immediately
  useEffect(() => {
    if (value.type === "file" && value.path) runProbe(value.path)
    else resetProbe()
  }, [value.type, value.path, runProbe, resetProbe])

  return (
    <div className="space-y-3">
      <ToggleGroup type="single" variant="outline" value={value.type} onValueChange={(t) => t && onChange(makeSource({ ...value, type: t as SourceSpec["type"] }))} className="flex-wrap">
        {TYPES.map((t) => (
          <ToggleGroupItem key={t.id} value={t.id} className="px-3 text-xs">{t.label}</ToggleGroupItem>
        ))}
      </ToggleGroup>

      {value.type === "test_pattern" && (
        <Field label="Pattern">
          <Select value={value.pattern} onValueChange={(p) => onChange({ ...value, pattern: p as SourceSpec["pattern"] })}>
            <SelectTrigger className="w-60"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="testsrc2">Moving test pattern</SelectItem>
              <SelectItem value="smptehdbars">SMPTE color bars</SelectItem>
              <SelectItem value="mandelbrot">Mandelbrot (busy scene)</SelectItem>
            </SelectContent>
          </Select>
        </Field>
      )}

      {(value.type === "file" || value.type === "image") && (
        <>
          <Field label={value.type === "file" ? "Video file on the server" : "Image file on the server"}>
            <div className="flex gap-2">
              <Input className="font-mono text-xs" placeholder="D:\Footage\gate_day.mp4" value={value.path ?? ""} onChange={(e) => onChange({ ...value, path: e.target.value })} />
              <Button variant="secondary" onClick={() => setPicker(true)}><FolderOpen /> Browse…</Button>
            </div>
          </Field>
          {value.type === "file" && value.path && (
            <div className="rounded-md border px-3 py-2 text-xs">
              {probe.isPending && <span className="flex items-center gap-2 text-muted-foreground"><Loader2 className="size-3.5 animate-spin" /> Checking file…</span>}
              {probe.isError && <span className="flex items-center gap-2 text-destructive"><AlertCircle className="size-3.5" /> {(probe.error as Error).message}</span>}
              {probe.data && (
                <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <CheckCircle2 className="size-3.5 text-success" />
                  <span>{probe.data.video.codec?.toUpperCase()}</span>
                  <span>{fmtRes(probe.data.video.width, probe.data.video.height)}</span>
                  <span>{probe.data.video.fps} fps</span>
                  <span>{fmtDuration(probe.data.duration_s)}</span>
                  <span className="text-muted-foreground">{probe.data.audio ? `audio ${probe.data.audio.codec}` : "no audio"}</span>
                </span>
              )}
            </div>
          )}
          {showOffset && value.type === "file" && (
            <Field label="Start offset (seconds)" hint="Cameras sharing one file look different when they start at different points.">
              <Input type="number" min={0} step={0.5} className="w-32" value={value.start_offset} onChange={(e) => onChange({ ...value, start_offset: Number(e.target.value) || 0 })} />
            </Field>
          )}
          <PathPickerDialog open={picker} onOpenChange={setPicker} accept={value.type === "file" ? "video" : "image"} onPick={(p) => onChange({ ...value, path: p })} />
        </>
      )}

      {value.type === "rtsp" && (
        <Field label="RTSP URL of a real camera" hint="Re-published as this virtual camera.">
          <Input className="font-mono text-xs" placeholder="rtsp://user:pass@192.168.1.50:554/stream1" value={value.url ?? ""} onChange={(e) => onChange({ ...value, url: e.target.value })} />
        </Field>
      )}
    </div>
  )
}

export function StreamModePicker({ value, onChange }: { value: "encode" | "passthrough"; onChange: (v: "encode" | "passthrough") => void }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {([
        ["encode", "Encode", "Live encoding. Every setting (resolution, bitrate, image, PTZ, OSD) really changes the video. ~1.2 CPU cores per 1080p camera."],
        ["passthrough", "Passthrough", "Streams pre-encoded copies of a file. Almost no CPU (~0.05 cores): use for many cameras."],
      ] as const).map(([id, label, desc]) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={`rounded-lg border p-3 text-left text-sm transition-colors ${value === id ? "border-primary bg-primary/10" : "hover:bg-muted"}`}
        >
          <div className="font-medium">{label}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">{desc}</div>
        </button>
      ))}
    </div>
  )
}
