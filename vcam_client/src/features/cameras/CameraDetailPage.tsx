import { ArrowLeft, ExternalLink, Gauge, Image as ImageIcon, MoreHorizontal, Pencil, Play, Power, RefreshCw, RotateCcw, Square, Trash2 } from "lucide-react"
import { lazy, Suspense, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { managerWhepUrl, snapshotUrl } from "@/api/client"
import { ptzApi, useCamera, useCameraControl, useDeleteCamera, usePatchCamera, usePtzStatus } from "@/api/queries"
import type { Camera } from "@/api/types"
import { ErrorState, Field, Loading, Section } from "@/components/common"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { CopyField } from "@/components/CopyField"
import { LivePlayer } from "@/components/LivePlayer"
import { PtzPad } from "@/components/PtzPad"
import { FaultBadge, StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { getToken } from "@/lib/auth/session"
import { cn } from "@/lib/utils"

const TABS = [
  { id: "overview", label: "Overview", load: () => import("./tabs/OverviewTab").then((m) => ({ default: m.OverviewTab })) },
  { id: "source", label: "Source", load: () => import("./tabs/SourceTab").then((m) => ({ default: m.SourceTab })) },
  { id: "streams", label: "Streams", load: () => import("./tabs/StreamsTab").then((m) => ({ default: m.StreamsTab })) },
  { id: "image", label: "Image", load: () => import("./tabs/ImageTab").then((m) => ({ default: m.ImageTab })) },
  { id: "osd", label: "OSD", load: () => import("./tabs/OsdTab").then((m) => ({ default: m.OsdTab })) },
  { id: "events", label: "I/O & Events", load: () => import("./tabs/EventsTab").then((m) => ({ default: m.EventsTab })) },
  { id: "faults", label: "Faults", load: () => import("./tabs/FaultsTab").then((m) => ({ default: m.FaultsTab })) },
  { id: "users", label: "Users", load: () => import("./tabs/UsersTab").then((m) => ({ default: m.UsersTab })) },
  { id: "network", label: "Network & Time", load: () => import("./tabs/NetworkTab").then((m) => ({ default: m.NetworkTab })) },
  { id: "identity", label: "Identity", load: () => import("./tabs/IdentityTab").then((m) => ({ default: m.IdentityTab })) },
  { id: "onvif", label: "ONVIF", load: () => import("./tabs/OnvifTab").then((m) => ({ default: m.OnvifTab })) },
  { id: "log", label: "Log", load: () => import("./tabs/LogTab").then((m) => ({ default: m.LogTab })) },
] as const

const LAZY = Object.fromEntries(TABS.map((t) => [t.id, lazy(t.load)])) as Record<string, React.ComponentType<{ camera: Camera }>>

export function CameraDetailPage() {
  const { id: idParam, tab = "overview" } = useParams()
  const id = Number(idParam)
  const navigate = useNavigate()
  const camera = useCamera(id)

  if (camera.isLoading) return <Loading />
  if (camera.isError) return <ErrorState error={camera.error} onRetry={() => camera.refetch()} />
  const c = camera.data!
  const Tab = LAZY[tab] ?? LAZY.overview

  return (
    <>
      <Header c={c} />
      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <LiveSection c={c} />
        <div className="space-y-4">
          <Section title="Connection" description="Paste these into your NVR">
            <div className="space-y-1.5">
              <CopyField label="ONVIF" value={c.urls.onvif} />
              {Object.entries(c.urls.rtsp).map(([k, v]) => <CopyField key={k} label={`RTSP ${k}`} value={v} />)}
              <CopyField label="Snapshot" value={Object.values(c.urls.snapshot)[0] ?? ""} />
              <div className="flex items-center gap-2 pt-1 text-xs text-muted-foreground">
                <span className="w-20">Web page</span>
                <a href={c.urls.web} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">{c.urls.web} <ExternalLink className="size-3" /></a>
              </div>
              <div className="pt-1 text-xs text-muted-foreground">Login: camera users (Users tab). Default <span className="font-mono">admin / admin123</span></div>
            </div>
          </Section>
          {c.has_ptz && <PtzSection c={c} />}
        </div>
      </div>

      <Tabs value={tab} onValueChange={(t) => navigate(`/cameras/${id}/${t}`, { replace: true })} className="mt-5">
        <div className="overflow-x-auto">
          <TabsList variant="line" className="w-max">
            {TABS.map((t) => (
              <TabsTrigger key={t.id} value={t.id} className="px-3">
                {t.label}
                {t.id === "faults" && c.faults.length > 0 && <span className="ml-1 rounded-full bg-status-fault/25 px-1.5 text-[10px] text-status-fault">{c.faults.length}</span>}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
      </Tabs>
      <div className="mt-4">
        <Suspense fallback={<Loading />}>
          <Tab camera={c} />
        </Suspense>
      </div>
    </>
  )
}

function Header({ c }: { c: Camera }) {
  const control = useCameraControl()
  const patch = usePatchCamera(c.id)
  const del = useDeleteCamera()
  const navigate = useNavigate()
  const [dialog, setDialog] = useState<null | "rename" | "port" | "delete" | "reset">(null)
  const [value, setValue] = useState("")
  const act = (action: "start" | "stop" | "restart" | "reboot" | "factory-reset") => control.mutate({ id: c.id, action, name: c.name })
  const running = c.status === "running"

  return (
    <div className="flex flex-wrap items-start gap-3">
      <Button asChild variant="ghost" size="icon-sm" className="mt-1"><Link to="/cameras" aria-label="Back"><ArrowLeft /></Link></Button>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="truncate text-xl font-semibold tracking-tight">{c.name}</h1>
          <StatusBadge status={c.status} />
          <FaultBadge count={c.faults.length} />
          {!c.enabled && <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">disabled</span>}
        </div>
        <div className="mt-0.5 text-sm text-muted-foreground">
          {c.identity.manufacturer} {c.identity.model} · S/N <span className="font-mono">{c.identity.serial_number}</span> · cam{String(c.number).padStart(3, "0")} · {c.ip}:{c.http_port}
        </div>
        {c.last_error && <div className="mt-1 text-xs text-status-error">{c.last_error}</div>}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {running ? <Button variant="outline" size="sm" onClick={() => act("stop")}><Square /> Stop</Button> : <Button size="sm" onClick={() => act("start")}><Play /> Start</Button>}
        <Button variant="outline" size="sm" onClick={() => act("restart")}><RefreshCw /> Restart</Button>
        <Button variant="outline" size="sm" disabled={!running} onClick={() => act("reboot")}><RotateCcw /> Reboot</Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button variant="outline" size="icon-sm" aria-label="More"><MoreHorizontal /></Button></DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuItem onSelect={() => { setValue(c.name); setDialog("rename") }}><Pencil /> Rename</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => { setValue(String(c.http_port)); setDialog("port") }}><Gauge /> Change port</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => patch.mutate({ enabled: !c.enabled })}><Power /> {c.enabled ? "Disable" : "Enable"}</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setDialog("reset")}><RotateCcw /> Factory reset</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={() => setDialog("delete")}><Trash2 /> Delete</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <Dialog open={dialog === "rename" || dialog === "port"} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{dialog === "rename" ? "Rename camera" : "Change HTTP/ONVIF port"}</DialogTitle></DialogHeader>
          <Field label={dialog === "rename" ? "Name" : "Port"} hint={dialog === "port" ? "The camera restarts on the new port. NVRs must be updated." : "Also updates the ONVIF name scope and the name OSD."}>
            <Input autoFocus type={dialog === "port" ? "number" : "text"} value={value} onChange={(e) => setValue(e.target.value)} />
          </Field>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialog(null)}>Cancel</Button>
            <Button disabled={!value || patch.isPending} onClick={() => patch.mutate(dialog === "rename" ? { name: value } : { http_port: Number(value) }, { onSuccess: () => setDialog(null) })}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ConfirmDialog open={dialog === "delete"} onOpenChange={(o) => !o && setDialog(null)} title={`Delete ${c.name}?`} description="NVRs using this camera will lose it." confirmLabel="Delete" onConfirm={() => del.mutate(c, { onSuccess: () => navigate("/cameras") })} />
      <ConfirmDialog open={dialog === "reset"} onOpenChange={(o) => !o && setDialog(null)} title="Factory reset?" description="Streams, image, OSD and PTZ settings go back to the model defaults, then the camera reboots. Network settings, users and footage are kept." confirmLabel="Reset and reboot" onConfirm={() => act("factory-reset")} />
    </div>
  )
}

function LiveSection({ c }: { c: Camera }) {
  const streams = c.streams.map((s) => s.key)
  // Browsers do not all decode H.265 over WebRTC: start on the first H.264 stream
  const firstH264 = c.streams.find((s) => s.encoding === "H264")?.key ?? streams[0]
  const [stream, setStream] = useState(firstH264)
  const [overlay, setOverlay] = useState(true)
  const info = c.streams.find((s) => s.key === stream)
  return (
    <Section
      title="Live"
      actions={
        <div className="flex items-center gap-2">
          <ToggleGroup type="single" size="sm" variant="outline" value={stream} onValueChange={(v) => v && setStream(v)}>
            {c.streams.map((s) => <ToggleGroupItem key={s.key} value={s.key} className="px-2.5 text-xs">{s.key} · {s.encoding}</ToggleGroupItem>)}
          </ToggleGroup>
          <Button variant="ghost" size="icon-sm" title="Stats overlay" className={cn(overlay && "text-primary")} onClick={() => setOverlay((o) => !o)}><Gauge /></Button>
          <Button asChild variant="ghost" size="icon-sm" title="Open snapshot"><a href={snapshotUrl(c.id, Date.now())} target="_blank" rel="noreferrer"><ImageIcon /></a></Button>
        </div>
      }
    >
      {c.status === "running" ? (
        <LivePlayer key={`${c.id}-${stream}`} whepUrl={managerWhepUrl(c.id, stream)} headers={{ Authorization: `Bearer ${getToken() ?? ""}` }} snapshotUrl={(b) => snapshotUrl(c.id, b)} overlay={overlay} className="aspect-video w-full" />
      ) : (
        <div className="grid aspect-video w-full place-items-center rounded-lg bg-video text-sm text-muted-foreground">Camera is {c.status}</div>
      )}
      {info?.encoding === "H265" && <div className="mt-2 text-xs text-warning">H.265 over WebRTC needs a recent browser with hardware decoding. If it stays black, switch to an H.264 stream.</div>}
    </Section>
  )
}

function PtzSection({ c }: { c: Camera }) {
  const status = usePtzStatus(c.id, c.status === "running")
  return (
    <Section title="PTZ" description="Same virtual PTZ the NVR drives over ONVIF">
      <PtzPad
        actions={{
          move: (p, t, z) => ptzApi.move(c.id, p, t, z),
          stop: () => ptzApi.stop(c.id),
          home: () => ptzApi.home(c.id),
          gotoPreset: (tok) => ptzApi.goto(c.id, tok),
        }}
        position={status.data}
        presets={status.data?.presets}
      />
    </Section>
  )
}
