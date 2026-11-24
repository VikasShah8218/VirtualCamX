import { FilePlus2, RotateCw, Trash2 } from "lucide-react"
import { useState } from "react"
import { useCameras, useDeleteMedia, useJobs, useMedia, useRegisterMedia, useRetryJobs } from "@/api/queries"
import { EmptyState, Field, PageHeader, Section } from "@/components/common"
import { PathPickerDialog } from "@/components/PathPickerDialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { fmtBytes, fmtDuration, fmtRes } from "@/lib/format"
import { baseName } from "@/lib/source"
import { cn } from "@/lib/utils"

/** Footage registered by path (used in place) + the passthrough cache jobs. */
export function MediaPage() {
  const media = useMedia()
  const jobs = useJobs()
  const cameras = useCameras()
  const register = useRegisterMedia()
  const del = useDeleteMedia()
  const retry = useRetryJobs()
  const [picker, setPicker] = useState(false)
  const [path, setPath] = useState("")
  const [label, setLabel] = useState("")
  const names = new Map((cameras.data ?? []).map((c) => [c.id, c.name]))
  const inUse = new Set((cameras.data ?? []).filter((c) => c.source.path).map((c) => c.source.path!))
  const unregistered = [...inUse].filter((p) => !(media.data ?? []).some((m) => m.path === p))

  return (
    <>
      <PageHeader title="Media library" description="Footage files on the VirtualCamX server. Files are used in place: never uploaded, copied or moved." />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          <Section title="Register footage" description="Optional: any path can also be used directly when creating a camera.">
            <div className="flex flex-wrap items-end gap-2">
              <Field label="File path" className="min-w-72 flex-1"><Input className="font-mono text-xs" value={path} placeholder="D:\Footage\gate_day.mp4" onChange={(e) => setPath(e.target.value)} /></Field>
              <Button variant="secondary" onClick={() => setPicker(true)}>Browse…</Button>
              <Field label="Label"><Input value={label} placeholder="Gate, day" onChange={(e) => setLabel(e.target.value)} /></Field>
              <Button disabled={!path || register.isPending} onClick={() => register.mutate({ path, label }, { onSuccess: () => { setPath(""); setLabel("") } })}><FilePlus2 /> Register</Button>
            </div>
            <PathPickerDialog open={picker} onOpenChange={setPicker} onPick={(p) => { setPath(p); if (!label) setLabel(baseName(p)) }} />
          </Section>

          {(media.data ?? []).length === 0 && unregistered.length === 0 ? (
            <EmptyState title="No footage yet">Register a video file, or pick one directly when you create a camera.</EmptyState>
          ) : (
            <div className="overflow-hidden rounded-xl border bg-card">
              <Table>
                <TableHeader>
                  <TableRow><TableHead>Footage</TableHead><TableHead>Video</TableHead><TableHead>Length</TableHead><TableHead>Size</TableHead><TableHead>Used by</TableHead><TableHead className="w-10" /></TableRow>
                </TableHeader>
                <TableBody>
                  {(media.data ?? []).map((m) => (
                    <TableRow key={m.id}>
                      <TableCell>
                        <div className="font-medium">{m.label || baseName(m.path)}</div>
                        <div className="max-w-md truncate font-mono text-[11px] text-muted-foreground" title={m.path}>{m.path}</div>
                      </TableCell>
                      <TableCell className="text-xs">{m.probe ? `${m.probe.video.codec?.toUpperCase()} ${fmtRes(m.probe.video.width, m.probe.video.height)} ${m.probe.video.fps}fps` : "—"}</TableCell>
                      <TableCell className="text-xs">{fmtDuration(m.probe?.duration_s)}</TableCell>
                      <TableCell className="text-xs">{fmtBytes(m.probe?.size_bytes)}</TableCell>
                      <TableCell className="text-xs">{m.used_by.length ? m.used_by.map((id) => names.get(id) ?? `#${id}`).slice(0, 3).join(", ") + (m.used_by.length > 3 ? ` +${m.used_by.length - 3}` : "") : "—"}</TableCell>
                      <TableCell><Button variant="ghost" size="icon-sm" aria-label="Remove from library" onClick={() => del.mutate(m.id)}><Trash2 /></Button></TableCell>
                    </TableRow>
                  ))}
                  {unregistered.map((p) => (
                    <TableRow key={p}>
                      <TableCell>
                        <div className="font-medium">{baseName(p)} <span className="text-xs text-muted-foreground">(used, not registered)</span></div>
                        <div className="max-w-md truncate font-mono text-[11px] text-muted-foreground">{p}</div>
                      </TableCell>
                      <TableCell colSpan={4} />
                      <TableCell><Button variant="ghost" size="icon-sm" aria-label="Register" onClick={() => register.mutate({ path: p, label: baseName(p) })}><FilePlus2 /></Button></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        <Section
          title="Passthrough cache"
          description="For Passthrough cameras each stream profile is encoded once, then copied without CPU cost."
          actions={(jobs.data ?? []).some((j) => j.status === "failed") && <Button size="xs" variant="outline" onClick={() => retry.mutate(undefined)}><RotateCw /> Retry failed</Button>}
        >
          {(jobs.data ?? []).length === 0 ? (
            <div className="py-3 text-sm text-muted-foreground">No cache jobs since the server started.</div>
          ) : (
            <div className="space-y-2">
              {(jobs.data ?? []).map((j) => (
                <div key={j.path + j.profile_key} className="rounded-md border px-2.5 py-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">{baseName(j.path)}</span>
                    <span className={cn(j.status === "ready" ? "text-success" : j.status === "failed" ? "text-destructive" : "animate-pulse text-warning")}>{j.status}</span>
                  </div>
                  <div className="truncate font-mono text-muted-foreground">{j.profile_key}</div>
                  {j.error && <div className="mt-1 break-all text-destructive">{j.error}</div>}
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>
    </>
  )
}
