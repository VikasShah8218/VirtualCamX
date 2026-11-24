import { KeyRound, Palette, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { useAdmins, useCreateAdmin, useDeleteAdmin, useEditableSettings, useHealth, useMe, useNics, useServerSettings, useUpdateSettings } from "@/api/queries"
import { Field, KV, PageHeader, Section } from "@/components/common"
import { SaveBar } from "@/components/SaveBar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ChangePasswordDialog } from "@/features/auth/ChangePasswordDialog"
import { fmtDuration } from "@/lib/format"
import { applyTheme, currentTheme, THEMES, type ThemeId } from "@/lib/theme"
import { cn } from "@/lib/utils"

export function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-4 xl:grid-cols-2">
        <ThemeSection />
        <HealthSection />
        <EditableSettings />
        <AdminsSection />
        <NicsSection />
        <AllSettings />
      </div>
    </>
  )
}

function ThemeSection() {
  const [theme, setTheme] = useState<ThemeId>(currentTheme)
  return (
    <Section title="Theme" description="Saved in this browser. Colors are defined in one file: vcam_client/src/theme.css.">
      <div className="grid grid-cols-3 gap-2">
        {THEMES.map((t) => (
          <button key={t.id} type="button" onClick={() => { applyTheme(t.id); setTheme(t.id) }} data-theme={t.id}
            className={cn("rounded-lg border bg-background p-3 text-left text-foreground transition", theme === t.id ? "ring-2 ring-primary" : "opacity-80 hover:opacity-100")}>
            <div className="mb-2 flex gap-1">
              {["bg-primary", "bg-card", "bg-success", "bg-warning", "bg-danger"].map((c) => <span key={c} className={cn("size-4 rounded-full border", c)} />)}
            </div>
            <div className="flex items-center gap-1.5 text-sm font-medium"><Palette className="size-3.5" />{t.label}</div>
            <div className="text-xs text-muted-foreground">{t.description}</div>
          </button>
        ))}
      </div>
    </Section>
  )
}

function HealthSection() {
  const h = useHealth().data
  return (
    <Section title="Server">
      {!h ? <div className="text-sm text-muted-foreground">Loading…</div> : (
        <>
          <KV k="Host IP">{h.host_ip}</KV>
          <KV k="Addressing">{h.addr_mode} mode</KV>
          <KV k="Uptime">{fmtDuration(h.uptime_s)}</KV>
          <KV k="FFmpeg" mono>{h.ffmpeg?.version?.split(" ").slice(0, 3).join(" ") ?? "not found"}</KV>
          <KV k="FFmpeg features">{[h.ffmpeg?.libx264 && "x264", h.ffmpeg?.libx265 && "x265", h.ffmpeg?.zmq_filter && "zmq", h.ffmpeg?.drawtext && "drawtext"].filter(Boolean).join(" · ")}</KV>
          <KV k="MediaMTX">{h.mediamtx.running ? "running" : "stopped"}{h.mediamtx.restarts ? ` (${h.mediamtx.restarts} restarts)` : ""}</KV>
          <KV k="WS-Discovery">{h.ws_discovery.running ? `listening · ${h.ws_discovery.probes_seen} probes seen` : h.ws_discovery.error ?? "off"}</KV>
          {h.mediamtx.log_tail.length > 0 && <pre className="mt-2 max-h-32 overflow-auto rounded bg-muted p-2 font-mono text-[10px]">{h.mediamtx.log_tail.join("\n")}</pre>}
        </>
      )}
    </Section>
  )
}

const LABELS: Record<string, [string, string]> = {
  cam_default_user: ["Default camera user", "For new cameras"],
  cam_default_password: ["Default camera password", "For new cameras"],
  reboot_seconds: ["Reboot duration (s)", "How long a camera stays offline when rebooted"],
  wssec_time_tolerance_s: ["WS-Security time tolerance (s)", "0 = do not check the NVR's clock"],
  max_subscriptions_per_camera: ["Max event subscriptions per camera", ""],
  x264_preset: ["x264 preset", "ultrafast = less CPU, bigger streams"],
}

function EditableSettings() {
  const editable = useEditableSettings()
  const all = useServerSettings()
  const update = useUpdateSettings()
  const [draft, setDraft] = useState<Record<string, string>>({})
  const keys = editable.data ?? []
  const value = (k: string) => draft[k] ?? String(all.data?.[k] ?? "")
  const dirty = Object.keys(draft).length > 0
  return (
    <Section title="Runtime settings" description="Applied immediately and saved on the server. Ports and paths live in vcam_server/.env (restart needed).">
      <div className="grid gap-3 sm:grid-cols-2">
        {keys.map((k) => (
          <Field key={k} label={LABELS[k]?.[0] ?? k} hint={LABELS[k]?.[1]}>
            <Input value={value(k)} onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))} />
          </Field>
        ))}
      </div>
      <SaveBar dirty={dirty} saving={update.isPending} onReset={() => setDraft({})} onSave={() => update.mutate(draft, { onSuccess: () => setDraft({}) })} />
    </Section>
  )
}

function AdminsSection() {
  const admins = useAdmins()
  const me = useMe()
  const create = useCreateAdmin()
  const del = useDeleteAdmin()
  const [u, setU] = useState("")
  const [p, setP] = useState("")
  const [pwOpen, setPwOpen] = useState(false)
  return (
    <Section title="Manager admins" actions={<Button size="xs" variant="outline" onClick={() => setPwOpen(true)}><KeyRound /> Change my password</Button>}>
      <div className="space-y-1.5">
        {(admins.data ?? []).map((a) => (
          <div key={a.id} className="flex items-center gap-2 text-sm">
            <span className="font-mono">{a.username}</span>
            {a.username === me.data?.username && <span className="text-xs text-muted-foreground">(you)</span>}
            {a.must_change_password && <span className="text-xs text-warning">default password</span>}
            <Button className="ml-auto" variant="ghost" size="icon-xs" disabled={a.username === me.data?.username} onClick={() => del.mutate(a.id)} aria-label="Delete"><Trash2 /></Button>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <Field label="Username"><Input value={u} onChange={(e) => setU(e.target.value)} /></Field>
        <Field label="Password (min 6)"><Input type="password" value={p} onChange={(e) => setP(e.target.value)} /></Field>
        <Button disabled={!u || p.length < 6} onClick={() => create.mutate({ username: u, password: p }, { onSuccess: () => { setU(""); setP("") } })}><Plus /> Add admin</Button>
      </div>
      <ChangePasswordDialog open={pwOpen} onDone={() => setPwOpen(false)} />
    </Section>
  )
}

function NicsSection() {
  const nics = useNics()
  return (
    <Section title="Network interfaces" description="Of the VirtualCamX server">
      {(nics.data ?? []).map((n) => (
        <KV key={n.name + n.ip} k={<span className="flex items-center gap-2"><span className={cn("size-2 rounded-full", n.up ? "bg-success" : "bg-muted-foreground/40")} />{n.name}</span>} mono>{n.ip}/{n.netmask} {n.mac ?? ""}</KV>
      ))}
    </Section>
  )
}

function AllSettings() {
  const all = useServerSettings()
  return (
    <Section title="Effective settings (.env)" className="xl:col-span-2">
      <div className="grid gap-x-6 sm:grid-cols-2">
        {Object.entries(all.data ?? {}).map(([k, v]) => <KV key={k} k={k} mono>{String(v)}</KV>)}
      </div>
    </Section>
  )
}
