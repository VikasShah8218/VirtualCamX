import { useCameraClients } from "@/api/queries"
import type { Camera } from "@/api/types"
import { KV, Section } from "@/components/common"
import { StatusBadge } from "@/components/StatusBadge"
import { fmtAgo, fmtBytes, fmtKbps } from "@/lib/format"
import { useLiveStats } from "@/lib/realtime"
import { sourceLabel } from "@/lib/source"
import { cn } from "@/lib/utils"

export function OverviewTab({ camera: c }: { camera: Camera }) {
  const clients = useCameraClients(c.id)
  const { cameras } = useLiveStats()
  const live = cameras[c.id]
  const w = c.worker

  return (
    <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
      <Section title="Camera">
        <KV k="Status"><StatusBadge status={c.status} /></KV>
        <KV k="Booted">{c.boot_time ? fmtAgo(c.boot_time) : "—"}</KV>
        <KV k="Address" mono>{c.ip}:{c.http_port}</KV>
        <KV k="Model">{c.identity.model}</KV>
        <KV k="Firmware">{c.identity.firmware_version}</KV>
        <KV k="MAC" mono>{c.identity.mac}</KV>
        <KV k="Event subscriptions">{c.subscriptions}</KV>
      </Section>

      <Section title="Video pipeline" description="The FFmpeg worker that produces this camera's streams">
        <KV k="Worker"><span className={cn(w.status === "running" ? "text-status-running" : w.status === "error" || w.status === "backoff" ? "text-status-error" : "text-muted-foreground")}>{w.status}</span></KV>
        <KV k="Mode">{w.mode ?? c.stream_mode}{c.stream_mode === "passthrough" && w.mode === "encode" ? " (cache being built)" : ""}</KV>
        <KV k="Input">{w.input ?? "—"}</KV>
        <KV k="Source">{sourceLabel(c.source)}</KV>
        <KV k="Restarts">{w.restarts}</KV>
        <KV k="PID" mono>{w.pid ?? "—"}</KV>
        {w.last_error && <div className="mt-2 rounded-md bg-destructive/10 p-2 font-mono text-[11px] break-all text-destructive">{w.last_error}</div>}
      </Section>

      <Section title="Streams">
        <div className="space-y-2">
          {c.streams.map((s) => {
            const st = live?.streams[s.key]
            return (
              <div key={s.key} className="rounded-lg border px-3 py-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium capitalize">{s.key}</span>
                  <span className={cn("text-xs", st?.ready ? "text-status-running" : "text-muted-foreground")}>{st?.ready ? "publishing" : "not ready"}</span>
                </div>
                <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                  <span>{s.encoding}</span>
                  <span>{s.width}×{s.height}</span>
                  <span>{s.fps} fps</span>
                  <span>target {fmtKbps(s.bitrate_kbps)}</span>
                  <span className="text-foreground">actual {fmtKbps(st?.kbps)}</span>
                  <span>{st?.readers ?? 0} reader(s)</span>
                </div>
              </div>
            )
          })}
        </div>
      </Section>

      <Section title="RTSP clients" description="Who is pulling video right now" className="lg:col-span-2 xl:col-span-1">
        {(clients.data?.rtsp ?? []).length === 0 ? (
          <div className="py-3 text-sm text-muted-foreground">No RTSP clients.</div>
        ) : (
          <div className="space-y-1.5 text-sm">
            {clients.data!.rtsp.map((s) => (
              <div key={s.id ?? s.remoteAddr} className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs">{s.remoteAddr}</span>
                <span className="text-xs text-muted-foreground">{s.path?.split("/")[1]} · {s.transport} · {fmtBytes(s.bytesSent)}</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="ONVIF clients" description="NVRs / tools that talked ONVIF to this camera">
        {(clients.data?.onvif ?? []).length === 0 ? (
          <div className="py-3 text-sm text-muted-foreground">No ONVIF requests yet.</div>
        ) : (
          <div className="space-y-1.5 text-sm">
            {clients.data!.onvif.map((o) => (
              <div key={o.client_ip} className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs">{o.client_ip}</span>
                <span className="text-xs text-muted-foreground">{o.requests} requests · {o.users.join(", ") || "no login"} · {fmtAgo(o.last_seen)}</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Event subscriptions">
        {(clients.data?.subscriptions ?? []).length === 0 ? (
          <div className="py-3 text-sm text-muted-foreground">No active subscriptions.</div>
        ) : (
          <div className="space-y-1.5 text-sm">
            {clients.data!.subscriptions.map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-2">
                <span className="text-xs">{s.kind}{s.consumer ? ` → ${s.consumer}` : ""}</span>
                <span className="text-xs text-muted-foreground">{s.queued} queued</span>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  )
}
