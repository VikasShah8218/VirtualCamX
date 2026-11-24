import { useCameraState, usePutSection } from "@/api/queries"
import type { Camera, NetworkState, TimeState } from "@/api/types"
import { ErrorState, Field, Loading, Section } from "@/components/common"
import { SaveBar } from "@/components/SaveBar"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useDraft } from "@/lib/useDraft"

/** Common zones as POSIX TZ strings (what ONVIF uses). POSIX signs are inverted: IST = UTC-5:30. */
const ZONES: [string, string][] = [
  ["UTC0", "UTC"],
  ["UTC-5:30", "India (UTC+5:30)"],
  ["UTC-4", "Gulf (UTC+4)"],
  ["UTC-3", "Moscow / Riyadh (UTC+3)"],
  ["CET-1CEST", "Central Europe (UTC+1, DST)"],
  ["GMT0BST", "UK (UTC+0, DST)"],
  ["EST5EDT", "US Eastern (UTC-5, DST)"],
  ["PST8PDT", "US Pacific (UTC-8, DST)"],
  ["UTC-8", "China / Singapore (UTC+8)"],
  ["UTC-9", "Japan / Korea (UTC+9)"],
  ["UTC-10", "Sydney (UTC+10)"],
]

const list = (s: string) => s.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean)

export function NetworkTab({ camera: c }: { camera: Camera }) {
  const state = useCameraState(c.id)
  const saveNet = usePutSection(c.id, "network", "Network settings saved")
  const saveTime = usePutSection(c.id, "time", "Time settings saved")
  const net = useDraft<NetworkState>(state.data?.network)
  const time = useDraft<TimeState>(state.data?.time)

  if (state.isLoading || !net.draft || !time.draft) return <Loading />
  if (state.isError) return <ErrorState error={state.error} />
  const n = net.draft
  const t = time.draft
  const setN = (p: Partial<NetworkState>) => net.setDraft((d) => ({ ...d, ...p }))
  const setT = (p: Partial<TimeState>) => time.setDraft((d) => ({ ...d, ...p }))
  const knownZone = ZONES.some(([z]) => z === t.tz)

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Section title="Network" description="Reported to NVRs over ONVIF (GetNetworkInterfaces, GetDNS…). Not applied to the host network.">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Hostname"><Input value={n.hostname} onChange={(e) => setN({ hostname: e.target.value })} /></Field>
          <Field label="Reported IP" hint={`Empty = the real address (${c.ip})`}><Input value={n.reported_ip ?? ""} placeholder={c.ip} onChange={(e) => setN({ reported_ip: e.target.value || null })} /></Field>
          <Field label="Prefix length"><Input type="number" min={1} max={32} value={n.prefix_length} onChange={(e) => setN({ prefix_length: Number(e.target.value) || 24 })} /></Field>
          <Field label="Gateway"><Input value={n.gateway} onChange={(e) => setN({ gateway: e.target.value })} /></Field>
          <Field label="DNS servers"><Input value={n.dns.join(", ")} onChange={(e) => setN({ dns: list(e.target.value) })} /></Field>
          <Field label="NTP servers"><Input value={n.ntp.join(", ")} onChange={(e) => setN({ ntp: list(e.target.value) })} /></Field>
          <Field label="MTU"><Input type="number" value={n.mtu} onChange={(e) => setN({ mtu: Number(e.target.value) || 1500 })} /></Field>
          <Field label="WS-Discovery" hint="NonDiscoverable = NVR search won't find it">
            <Select value={n.discovery_mode} onValueChange={(v) => setN({ discovery_mode: v as NetworkState["discovery_mode"] })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="Discoverable">Discoverable</SelectItem><SelectItem value="NonDiscoverable">Not discoverable</SelectItem></SelectContent>
            </Select>
          </Field>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm"><Switch checked={n.dhcp} onCheckedChange={(v) => setN({ dhcp: v })} /> Report DHCP enabled</label>
        <SaveBar dirty={net.dirty} saving={saveNet.isPending} onReset={net.reset} onSave={() => saveNet.mutate(n, { onSuccess: net.saved })} />
      </Section>

      <Section title="Date & time" description="The camera clock. NVRs read it with GetSystemDateAndTime and use it for WS-Security.">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Time zone">
            <Select value={knownZone ? t.tz : "custom"} onValueChange={(v) => v !== "custom" && setT({ tz: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {ZONES.map(([z, label]) => <SelectItem key={z} value={z}>{label}</SelectItem>)}
                <SelectItem value="custom">Custom POSIX string…</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="POSIX TZ"><Input className="font-mono text-xs" value={t.tz} onChange={(e) => setT({ tz: e.target.value })} /></Field>
          <Field label="Mode">
            <Select value={t.date_time_type} onValueChange={(v) => setT({ date_time_type: v as TimeState["date_time_type"], offset_seconds: v === "NTP" ? 0 : t.offset_seconds })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="NTP">NTP (host time)</SelectItem><SelectItem value="Manual">Manual offset</SelectItem></SelectContent>
            </Select>
          </Field>
          <Field label="Offset from host (seconds)" hint="Manual mode: a wrong camera clock (NVR time-sync tests)">
            <Input type="number" disabled={t.date_time_type !== "Manual"} value={Math.round(t.offset_seconds)} onChange={(e) => setT({ offset_seconds: Number(e.target.value) || 0 })} />
          </Field>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm"><Switch checked={t.daylight_savings} onCheckedChange={(v) => setT({ daylight_savings: v })} /> Daylight saving flag</label>
        <SaveBar dirty={time.dirty} saving={saveTime.isPending} onReset={time.reset} onSave={() => saveTime.mutate(t, { onSuccess: time.saved })} />
      </Section>
    </div>
  )
}
