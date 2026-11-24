import { useEffect, useState } from "react"
import { useJobs, useSetSource } from "@/api/queries"
import type { Camera, SourceSpec } from "@/api/types"
import { Field, Section } from "@/components/common"
import { SaveBar } from "@/components/SaveBar"
import { SourcePicker, StreamModePicker } from "@/components/SourcePicker"
import { sourceLabel } from "@/lib/source"
import { cn } from "@/lib/utils"

export function SourceTab({ camera: c }: { camera: Camera }) {
  const setSource = useSetSource(c.id)
  const jobs = useJobs()
  const [source, setSrc] = useState<SourceSpec>(c.source)
  const [mode, setMode] = useState<"encode" | "passthrough">(c.stream_mode === "passthrough" ? "passthrough" : "encode")
  const serverKey = JSON.stringify([c.source, c.stream_mode])
  useEffect(() => {
    setSrc(c.source)
    setMode(c.stream_mode === "passthrough" ? "passthrough" : "encode")
  }, [serverKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = JSON.stringify(source) !== JSON.stringify(c.source) || (source.type === "file" && mode !== c.stream_mode)
  const fileJobs = (jobs.data ?? []).filter((j) => j.path === c.source.path)

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Section title="What the camera sees" description="Switching footage is live: NVRs only see a short RTSP reconnect.">
        <SourcePicker value={source} onChange={setSrc} />
        {source.type === "file" && (
          <Field label="Stream mode" className="mt-4">
            <StreamModePicker value={mode} onChange={setMode} />
          </Field>
        )}
        <SaveBar
          dirty={dirty}
          saving={setSource.isPending}
          note="Apply the new source (clients reconnect)"
          onReset={() => { setSrc(c.source); setMode(c.stream_mode === "passthrough" ? "passthrough" : "encode") }}
          onSave={() => setSource.mutate({ source, stream_mode: source.type === "file" ? mode : "encode" })}
        />
      </Section>
      <div className="space-y-4">
        <Section title="Now">
          <div className="space-y-1 text-sm">
            <div>{sourceLabel(c.source)}</div>
            {c.source.path && <div className="font-mono text-[11px] break-all text-muted-foreground">{c.source.path}</div>}
            <div className="text-xs text-muted-foreground">Mode: {c.worker.mode ?? c.stream_mode}{c.source.start_offset ? ` · starts at ${c.source.start_offset}s` : ""}</div>
          </div>
        </Section>
        {c.stream_mode === "passthrough" && (
          <Section title="Passthrough cache" description="Each stream profile is encoded once, then streamed without re-encoding.">
            {fileJobs.length === 0 ? (
              <div className="text-xs text-muted-foreground">No cache jobs for this file (the original already matches, or nothing needed).</div>
            ) : (
              <div className="space-y-1.5">
                {fileJobs.map((j) => (
                  <div key={j.profile_key} className="text-xs">
                    <div className="flex justify-between gap-2">
                      <span className="truncate font-mono">{j.profile_key}</span>
                      <span className={cn(j.status === "ready" ? "text-success" : j.status === "failed" ? "text-destructive" : "text-warning")}>{j.status}</span>
                    </div>
                    {j.error && <div className="text-destructive">{j.error}</div>}
                  </div>
                ))}
              </div>
            )}
          </Section>
        )}
      </div>
    </div>
  )
}
