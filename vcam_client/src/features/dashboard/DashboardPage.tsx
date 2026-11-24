import { AlertTriangle, Camera, Cpu, Gauge, Plus, Radio, Users, Wifi, Zap } from "lucide-react"
import { Link } from "react-router"
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts"
import { useCameras, useHealth, useStats } from "@/api/queries"
import { EmptyState, PageHeader, Section, StatTile } from "@/components/common"
import { FaultBadge, StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { EventFeed } from "@/features/events/EventFeed"
import { fmtKbps } from "@/lib/format"
import { useLiveStats, useStatsHistory } from "@/lib/realtime"
import { cn } from "@/lib/utils"

export function DashboardPage() {
  const cameras = useCameras()
  const polled = useStats()
  const live = useLiveStats()
  const history = useStatsHistory()
  const health = useHealth()
  const farm = live.farm ?? polled.data?.farm

  const attention = (cameras.data ?? []).filter((c) => c.status === "error" || c.status === "offline" || c.faults.length > 0 || c.worker.status === "error" || c.worker.status === "backoff")

  if (cameras.isSuccess && cameras.data.length === 0) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <EmptyState
          icon={<Camera className="size-10" />}
          title="No virtual cameras yet"
          action={
            <>
              <Button asChild><Link to="/cameras?new=1"><Plus /> Create a camera</Link></Button>
              <Button asChild variant="outline"><Link to="/cameras?bulk=1">Bulk create 20 cameras</Link></Button>
            </>
          }
        >
          Every virtual camera behaves like a real ONVIF IP camera: NVRs can discover it, add it, stream RTSP from it and receive its events.
        </EmptyState>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Live state of the virtual camera farm"
        actions={
          <>
            <Button asChild variant="outline"><Link to="/cameras?bulk=1">Bulk create</Link></Button>
            <Button asChild><Link to="/cameras?new=1"><Plus /> New camera</Link></Button>
          </>
        }
      />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <StatTile label="Cameras" value={farm?.cameras ?? "—"} icon={<Camera className="size-4" />} />
        <StatTile label="Running" value={farm?.running ?? "—"} tone="text-status-running" icon={<Radio className="size-4" />} />
        <StatTile label="Offline / rebooting" value={farm?.offline ?? "—"} tone={farm?.offline ? "text-status-offline" : undefined} />
        <StatTile label="Errors" value={farm?.error ?? "—"} tone={farm?.error ? "text-status-error" : undefined} icon={<AlertTriangle className="size-4" />} />
        <StatTile label="RTSP clients" value={farm?.rtsp_clients ?? "—"} sub={`${farm?.subscriptions ?? 0} event subscriptions`} icon={<Users className="size-4" />} />
        <StatTile label="Outgoing video" value={fmtKbps(farm?.kbps_out)} icon={<Gauge className="size-4" />} />
        <StatTile label="Host CPU / RAM" value={farm ? `${Math.round(farm.cpu_percent)}%` : "—"} sub={farm ? `RAM ${Math.round(farm.ram_percent)}%` : undefined} icon={<Cpu className="size-4" />} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Outgoing video (10 min)">
              <Spark data={history} dataKey="kbps" color="var(--chart-1)" format={fmtKbps} />
            </Section>
            <Section title="Host CPU (10 min)">
              <Spark data={history} dataKey="cpu" color="var(--chart-3)" format={(v) => `${Math.round(v)}%`} max={100} />
            </Section>
          </div>
          <Section title="Needs attention" description="Cameras with errors, offline state or active faults">
            {attention.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">All cameras are healthy.</div>
            ) : (
              <div className="divide-y">
                {attention.slice(0, 12).map((c) => (
                  <Link key={c.id} to={`/cameras/${c.id}`} className="flex items-center gap-3 py-2 text-sm hover:bg-muted/40">
                    <StatusBadge status={c.status} compact />
                    <span className="w-40 truncate font-medium">{c.name}</span>
                    <FaultBadge count={c.faults.length} />
                    <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                      {c.last_error || c.worker.last_error || c.faults.map((f) => f.type).join(", ")}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </Section>
        </div>
        <div className="space-y-4">
          <Section title="Live events" actions={<Link to="/events" className="text-xs text-primary hover:underline">Simulator</Link>}>
            <EventFeed limit={12} compact />
          </Section>
          <Section title="System health">
            {health.data ? (
              <div className="grid grid-cols-2 gap-2 text-sm">
                <Check ok={!!health.data.ffmpeg?.ok} label="FFmpeg" />
                <Check ok={!!health.data.ffmpeg?.zmq_filter} label="Live controls (zmq)" />
                <Check ok={health.data.mediamtx.running} label="MediaMTX" />
                <Check ok={health.data.ws_discovery.running} label="WS-Discovery" />
                <div className="col-span-2 mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                  <Wifi className="size-3.5" /> Host IP {health.data.host_ip} · {health.data.addr_mode} mode
                  <Zap className="ml-2 size-3.5" /> {health.data.ws_discovery.probes_seen} discovery probes
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">Checking…</div>
            )}
          </Section>
        </div>
      </div>
    </>
  )
}

function Check({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className={cn("size-2 rounded-full", ok ? "bg-success" : "bg-danger")} /> {label}
    </span>
  )
}

function Spark({ data, dataKey, color, format, max }: { data: object[]; dataKey: string; color: string; format: (v: number) => string; max?: number }) {
  if (data.length < 2) return <div className="grid h-28 place-items-center text-xs text-muted-foreground">Collecting samples…</div>
  return (
    <div className="h-28">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`g-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={[0, max ?? "auto"]} />
          <Tooltip
            contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
            labelFormatter={() => ""}
            formatter={(v) => [format(Number(v)), ""]}
          />
          <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} fill={`url(#g-${dataKey})`} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
