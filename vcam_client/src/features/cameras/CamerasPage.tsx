import { Camera as CameraIcon, LayoutGrid, Layers, List, Move3d, Plus, Search } from "lucide-react"
import { useMemo, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"
import { snapshotUrl } from "@/api/client"
import { useCameras } from "@/api/queries"
import type { Camera } from "@/api/types"
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common"
import { CopyButton } from "@/components/CopyField"
import { FaultBadge, StatusBadge, statusStyle } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { fmtKbps } from "@/lib/format"
import { useInterval } from "@/lib/useInterval"
import { useLiveStats } from "@/lib/realtime"
import { sourceLabel } from "@/lib/source"
import { readStored, writeStored } from "@/lib/storage"
import { cn } from "@/lib/utils"
import { BulkActionBar } from "./BulkActionBar"
import { BulkCreateDialog } from "./BulkCreateDialog"
import { CameraCreateDialog } from "./CameraCreateDialog"
import { CameraMenu } from "./CameraMenu"

const VIEW_KEY = "vcamx.cameras.view"
type SortKey = "number" | "name" | "status" | "port" | "kbps"

export function CamerasPage() {
  const cameras = useCameras()
  const { cameras: stats } = useLiveStats()
  const [params, setParams] = useSearchParams()
  const [view, setView] = useState<"table" | "grid">(() => readStored(VIEW_KEY, { view: "table" as "table" | "grid" }).view)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "number", dir: 1 })
  const q = params.get("q") ?? ""
  const status = params.get("status") ?? "all"
  const tpl = params.get("template") ?? "all"

  const setParam = (k: string, v: string | null) => {
    const p = new URLSearchParams(params)
    if (v && v !== "all") p.set(k, v)
    else p.delete(k)
    setParams(p, { replace: true })
  }

  const rows = useMemo(() => {
    const ql = q.toLowerCase()
    const list = (cameras.data ?? []).filter(
      (c) =>
        (status === "all" || c.status === status || (status === "faults" && c.faults.length > 0)) &&
        (tpl === "all" || c.template_key === tpl) &&
        (!ql || `${c.name} ${c.http_port} ${c.ip} cam${String(c.number).padStart(3, "0")} ${c.identity.model}`.toLowerCase().includes(ql)),
    )
    const val = (c: Camera): string | number =>
      sort.key === "name" ? c.name.toLowerCase() : sort.key === "status" ? c.status : sort.key === "port" ? c.http_port : sort.key === "kbps" ? (stats[c.id]?.kbps_in ?? 0) : c.number
    return [...list].sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * sort.dir)
  }, [cameras.data, q, status, tpl, sort, stats])

  const templates = [...new Set((cameras.data ?? []).map((c) => c.template_key))]
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id))
  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const changeView = (v: "table" | "grid") => { setView(v); writeStored(VIEW_KEY, { view: v }) }
  const sortBy = (key: SortKey) => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : 1 }))

  return (
    <>
      <PageHeader
        title="Cameras"
        description={cameras.data ? `${cameras.data.length} virtual cameras · ${cameras.data.filter((c) => c.status === "running").length} running` : undefined}
        actions={
          <>
            <Button variant="outline" onClick={() => setParam("bulk", "1")}><Layers /> Bulk create</Button>
            <Button onClick={() => setParam("new", "1")}><Plus /> New camera</Button>
          </>
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" placeholder="Search name, port, model…" value={q} onChange={(e) => setParam("q", e.target.value)} />
        </div>
        <Select value={status} onValueChange={(v) => setParam("status", v)}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {["running", "stopped", "offline", "rebooting", "error"].map((s) => <SelectItem key={s} value={s}>{statusStyle(s).label}</SelectItem>)}
            <SelectItem value="faults">With faults</SelectItem>
          </SelectContent>
        </Select>
        <Select value={tpl} onValueChange={(v) => setParam("template", v)}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All models</SelectItem>
            {templates.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
          </SelectContent>
        </Select>
        <ToggleGroup type="single" variant="outline" value={view} onValueChange={(v) => v && changeView(v as "table" | "grid")} className="ml-auto">
          <ToggleGroupItem value="table" aria-label="Table"><List /></ToggleGroupItem>
          <ToggleGroupItem value="grid" aria-label="Grid"><LayoutGrid /></ToggleGroupItem>
        </ToggleGroup>
      </div>

      {cameras.isLoading && <Loading />}
      {cameras.isError && <ErrorState error={cameras.error} onRetry={() => cameras.refetch()} />}
      {cameras.isSuccess && cameras.data.length === 0 && (
        <EmptyState
          icon={<CameraIcon className="size-10" />}
          title="Create your first virtual camera"
          action={<><Button onClick={() => setParam("new", "1")}><Plus /> New camera</Button><Button variant="outline" onClick={() => setParam("bulk", "1")}>Bulk create</Button></>}
        >
          Each camera gets its own port, answers ONVIF and WS-Discovery, and streams RTSP. Add it to your NVR with the ONVIF URL.
        </EmptyState>
      )}
      {cameras.isSuccess && cameras.data.length > 0 && rows.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground">No camera matches the filters.</div>}

      {rows.length > 0 && view === "table" && (
        <div className="overflow-hidden rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-9"><Checkbox checked={allSelected ? true : selected.size ? "indeterminate" : false} onCheckedChange={() => setSelected(allSelected ? new Set() : new Set(rows.map((r) => r.id)))} /></TableHead>
                <SortHead k="number" sort={sort} onSort={sortBy} className="w-14">#</SortHead>
                <SortHead k="name" sort={sort} onSort={sortBy}>Name</SortHead>
                <SortHead k="status" sort={sort} onSort={sortBy}>Status</SortHead>
                <SortHead k="port" sort={sort} onSort={sortBy}>Address</SortHead>
                <TableHead className="hidden lg:table-cell">Model</TableHead>
                <TableHead className="hidden xl:table-cell">Source</TableHead>
                <TableHead className="hidden md:table-cell">Streams</TableHead>
                <TableHead className="text-right">Clients</TableHead>
                <SortHead k="kbps" sort={sort} onSort={sortBy} className="text-right">Bitrate</SortHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => <CameraRow key={c.id} c={c} selected={selected.has(c.id)} onToggle={() => toggle(c.id)} readers={stats[c.id]?.readers} kbps={stats[c.id]?.kbps_in} />)}
            </TableBody>
          </Table>
        </div>
      )}

      {rows.length > 0 && view === "grid" && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {rows.map((c) => <CameraCard key={c.id} c={c} selected={selected.has(c.id)} onToggle={() => toggle(c.id)} />)}
        </div>
      )}

      <BulkActionBar ids={[...selected].filter((id) => rows.some((r) => r.id === id))} onClear={() => setSelected(new Set())} />
      <CameraCreateDialog open={params.get("new") === "1"} onOpenChange={(o) => setParam("new", o ? "1" : null)} />
      <BulkCreateDialog open={params.get("bulk") === "1"} onOpenChange={(o) => setParam("bulk", o ? "1" : null)} />
    </>
  )
}

function SortHead({ k, sort, onSort, children, className }: { k: SortKey; sort: { key: SortKey; dir: number }; onSort: (k: SortKey) => void; children: React.ReactNode; className?: string }) {
  return (
    <TableHead className={className}>
      <button type="button" className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => onSort(k)}>
        {children}
        {sort.key === k && <span className="text-[10px]">{sort.dir === 1 ? "▲" : "▼"}</span>}
      </button>
    </TableHead>
  )
}

function CameraRow({ c, selected, onToggle, readers, kbps }: { c: Camera; selected: boolean; onToggle: () => void; readers?: number; kbps?: number }) {
  const navigate = useNavigate()
  return (
    <TableRow data-state={selected ? "selected" : undefined} className="cursor-pointer" onClick={() => navigate(`/cameras/${c.id}`)}>
      <TableCell onClick={(e) => e.stopPropagation()}><Checkbox checked={selected} onCheckedChange={onToggle} /></TableCell>
      <TableCell className="font-mono text-xs text-muted-foreground">{String(c.number).padStart(3, "0")}</TableCell>
      <TableCell>
        <div className="flex items-center gap-2 font-medium">
          {c.name}
          {c.has_ptz && <Move3d className="size-3.5 text-primary" aria-label="PTZ" />}
          <FaultBadge count={c.faults.length} />
        </div>
      </TableCell>
      <TableCell><StatusBadge status={c.status} /></TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}>
        <span className="inline-flex items-center gap-1 font-mono text-xs">
          {c.ip}:{c.http_port}
          <CopyButton value={c.urls.onvif} label="" />
        </span>
      </TableCell>
      <TableCell className="hidden text-xs text-muted-foreground lg:table-cell">{c.identity.model}</TableCell>
      <TableCell className="hidden max-w-48 truncate text-xs xl:table-cell" title={c.source.path ?? undefined}>
        {sourceLabel(c.source)}
        {c.source.type === "file" && <span className={cn("ml-1.5 rounded px-1 py-0.5 text-[10px]", c.worker.mode === "passthrough" ? "bg-success/15 text-success" : "bg-muted text-muted-foreground")}>{c.worker.mode ?? c.stream_mode}</span>}
      </TableCell>
      <TableCell className="hidden text-xs text-muted-foreground md:table-cell">
        {c.streams.map((s) => `${s.encoding} ${s.height}p`).join(" · ")}
      </TableCell>
      <TableCell className="text-right tabular-nums">{readers ?? 0}</TableCell>
      <TableCell className="text-right text-xs tabular-nums">{fmtKbps(kbps)}</TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}><CameraMenu camera={c} /></TableCell>
    </TableRow>
  )
}

function CameraCard({ c, selected, onToggle }: { c: Camera; selected: boolean; onToggle: () => void }) {
  const [bust, setBust] = useState(() => Date.now())
  useInterval(() => setBust(Date.now()), c.status === "running" ? 5000 : null)
  return (
    <div className={cn("group overflow-hidden rounded-xl border bg-card", selected && "ring-2 ring-primary")}>
      <Link to={`/cameras/${c.id}`} className="relative block aspect-video bg-video">
        {c.status === "running" ? (
          <img src={snapshotUrl(c.id, bust)} alt="" loading="lazy" className="size-full object-cover" onError={(e) => (e.currentTarget.style.visibility = "hidden")} onLoad={(e) => (e.currentTarget.style.visibility = "visible")} />
        ) : (
          <div className="grid size-full place-items-center text-xs text-muted-foreground">{statusStyle(c.status).label}</div>
        )}
        <div className="absolute top-2 left-2 rounded bg-background/75 px-1.5 py-0.5"><StatusBadge status={c.status} /></div>
      </Link>
      <div className="flex items-center gap-2 p-2.5">
        <Checkbox checked={selected} onCheckedChange={onToggle} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 truncate text-sm font-medium">{c.name}<FaultBadge count={c.faults.length} /></div>
          <div className="truncate font-mono text-[11px] text-muted-foreground">{c.ip}:{c.http_port} · {c.identity.model}</div>
        </div>
        <CameraMenu camera={c} />
      </div>
    </div>
  )
}
