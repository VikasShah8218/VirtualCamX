import { Copy, Download, Pause, Play, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { useCameras, useClearInspector, useInspector, useInspectorEntry } from "@/api/queries"
import type { InspectorSummary } from "@/api/types"
import { copyText } from "@/components/CopyField"
import { Loading } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { fmtTime } from "@/lib/format"
import { cn } from "@/lib/utils"
import { prettyXml, tokenizeXml } from "@/lib/xml"
import { toast } from "sonner"

/**
 * Every ONVIF request NVRs sent to the virtual cameras, with the full SOAP request/response.
 * The main tool for "why does my NVR not add this camera?".
 */
export function InspectorView({ cameraId }: { cameraId?: number }) {
  const cameras = useCameras()
  const [cam, setCam] = useState<string>(cameraId ? String(cameraId) : "all")
  const [op, setOp] = useState("")
  const [client, setClient] = useState("")
  const [follow, setFollow] = useState(true)
  const [onlyFaults, setOnlyFaults] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const clear = useClearInspector()
  const effectiveCam = cameraId ?? (cam === "all" ? undefined : Number(cam))
  const list = useInspector({ camera_id: effectiveCam, op: op || undefined, client_ip: client || undefined }, follow)
  const names = useMemo(() => new Map((cameras.data ?? []).map((c) => [c.id, c.name])), [cameras.data])
  const rows = (list.data ?? []).filter((r) => !onlyFaults || r.fault || r.status >= 400)

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="min-w-0 rounded-xl border bg-card">
        <div className="flex flex-wrap items-center gap-2 border-b p-2.5">
          {!cameraId && (
            <Select value={cam} onValueChange={setCam}>
              <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All cameras</SelectItem>
                {(cameras.data ?? []).map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          )}
          <Input className="w-40" placeholder="Operation" value={op} onChange={(e) => setOp(e.target.value)} />
          <Input className="w-36" placeholder="Client IP" value={client} onChange={(e) => setClient(e.target.value)} />
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input type="checkbox" checked={onlyFaults} onChange={(e) => setOnlyFaults(e.target.checked)} /> Only failures
          </label>
          <div className="ml-auto flex gap-1">
            <Button size="sm" variant={follow ? "secondary" : "ghost"} onClick={() => setFollow((f) => !f)}>{follow ? <Pause /> : <Play />} {follow ? "Following" : "Paused"}</Button>
            <Button size="icon-sm" variant="ghost" aria-label="Clear" onClick={() => clear.mutate(effectiveCam)}><Trash2 /></Button>
          </div>
        </div>
        {list.isLoading ? <Loading /> : (
          <div className="max-h-[65vh] overflow-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card text-muted-foreground">
                <tr className="border-b text-left">
                  <th className="px-2.5 py-2 font-medium">Time</th>
                  {!cameraId && <th className="px-2 py-2 font-medium">Camera</th>}
                  <th className="px-2 py-2 font-medium">Client</th>
                  <th className="px-2 py-2 font-medium">Operation</th>
                  <th className="px-2 py-2 font-medium">Auth</th>
                  <th className="px-2 py-2 text-right font-medium">HTTP</th>
                  <th className="px-2.5 py-2 text-right font-medium">ms</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && <tr><td colSpan={7} className="py-10 text-center text-muted-foreground">No ONVIF requests yet. Add a camera to an NVR or run tools/onvif_smoke.py.</td></tr>}
                {rows.map((r) => <Row key={r.id} r={r} cameraName={names.get(r.camera_id)} showCamera={!cameraId} selected={selected === r.id} onSelect={() => setSelected(r.id)} />)}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <EntryDetail id={selected} />
    </div>
  )
}

function Row({ r, cameraName, showCamera, selected, onSelect }: { r: InspectorSummary; cameraName?: string; showCamera: boolean; selected: boolean; onSelect: () => void }) {
  const bad = r.status >= 400 || !!r.fault
  return (
    <tr onClick={onSelect} className={cn("cursor-pointer border-b border-border/40 hover:bg-muted/50", bad && "bg-destructive/10", selected && "bg-accent")}>
      <td className="px-2.5 py-1.5 font-mono whitespace-nowrap tabular-nums">{fmtTime(r.ts)}</td>
      {showCamera && <td className="max-w-28 truncate px-2 py-1.5">{cameraName ?? `#${r.camera_id}`}</td>}
      <td className="px-2 py-1.5 font-mono">{r.client_ip}</td>
      <td className="px-2 py-1.5"><span className="text-muted-foreground">{r.service}.</span>{r.operation}</td>
      <td className={cn("px-2 py-1.5", r.auth === "failed" && "text-destructive")}>{r.auth}{r.user ? ` (${r.user})` : ""}</td>
      <td className={cn("px-2 py-1.5 text-right tabular-nums", bad && "text-destructive")}>{r.status}</td>
      <td className="px-2.5 py-1.5 text-right tabular-nums">{r.duration_ms}</td>
    </tr>
  )
}

function EntryDetail({ id }: { id: number | null }) {
  const entry = useInspectorEntry(id)
  if (id == null) return <div className="grid min-h-60 place-items-center rounded-xl border border-dashed text-sm text-muted-foreground">Select a request to see its SOAP XML</div>
  if (entry.isLoading || !entry.data) return <div className="rounded-xl border"><Loading /></div>
  const e = entry.data
  return (
    <div className="min-w-0 rounded-xl border bg-card p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3 text-sm">
        <span className="font-semibold">{e.service}.{e.operation}</span>
        <span className="text-xs text-muted-foreground">{e.client_ip} · {e.path} · auth {e.auth} ({e.auth_method}) · {e.duration_ms} ms</span>
      </div>
      {e.fault && <div className="mb-2 rounded-md bg-destructive/10 px-2 py-1.5 font-mono text-xs text-destructive">{e.fault}</div>}
      <Tabs defaultValue="request">
        <TabsList><TabsTrigger value="request">Request</TabsTrigger><TabsTrigger value="response">Response</TabsTrigger></TabsList>
        <TabsContent value="request"><XmlBlock xml={e.request_xml} name={`${e.operation}-request.xml`} /></TabsContent>
        <TabsContent value="response"><XmlBlock xml={e.response_xml} name={`${e.operation}-response.xml`} /></TabsContent>
      </Tabs>
    </div>
  )
}

const TOKEN_CLASS = { tag: "text-primary", attr: "text-chart-4", value: "text-chart-2", text: "text-foreground", punct: "text-muted-foreground" } as const

function XmlBlock({ xml, name }: { xml: string; name: string }) {
  const pretty = useMemo(() => prettyXml(xml), [xml])
  const tokens = useMemo(() => tokenizeXml(pretty), [pretty])
  const download = () => {
    const url = URL.createObjectURL(new Blob([pretty], { type: "application/xml" }))
    const a = document.createElement("a")
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="relative">
      <div className="absolute top-1.5 right-1.5 flex gap-1">
        <Button size="icon-xs" variant="secondary" aria-label="Copy XML" onClick={() => copyText(pretty).then(() => toast.success("XML copied"))}><Copy /></Button>
        <Button size="icon-xs" variant="secondary" aria-label="Download XML" onClick={download}><Download /></Button>
      </div>
      <pre className="max-h-[58vh] overflow-auto rounded-md bg-muted p-3 font-mono text-[11px] leading-relaxed whitespace-pre">
        {tokens.map((t, i) => <span key={i} className={TOKEN_CLASS[t.kind]}>{t.text}</span>)}
      </pre>
    </div>
  )
}
