import { RefreshCw } from "lucide-react"
import { useCameraState, usePutSection } from "@/api/queries"
import type { Camera, Identity } from "@/api/types"
import { ErrorState, Field, Loading, Section } from "@/components/common"
import { SaveBar } from "@/components/SaveBar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useDraft } from "@/lib/useDraft"

function randomMac() {
  const b = Array.from({ length: 6 }, () => Math.floor(Math.random() * 256))
  b[0] = (b[0] & 0xfc) | 0x02 // locally administered, unicast
  return b.map((x) => x.toString(16).padStart(2, "0").toUpperCase()).join(":")
}

export function IdentityTab({ camera: c }: { camera: Camera }) {
  const state = useCameraState(c.id)
  const saveId = usePutSection(c.id, "identity", "Identity saved")
  const saveScopes = usePutSection(c.id, "scopes", "Scopes saved")
  const ident = useDraft<Identity>(state.data?.identity)
  const scopes = useDraft<string[]>(state.data?.scopes)

  if (state.isLoading || !ident.draft || !scopes.draft) return <Loading />
  if (state.isError) return <ErrorState error={state.error} />
  const d = ident.draft
  const set = (p: Partial<Identity>) => ident.setDraft((x) => ({ ...x, ...p }))

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Section title="Device identity" description="Returned by ONVIF GetDeviceInformation. Change it to test how an NVR handles other vendors / models.">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Manufacturer"><Input value={d.manufacturer} onChange={(e) => set({ manufacturer: e.target.value })} /></Field>
          <Field label="Model"><Input value={d.model} onChange={(e) => set({ model: e.target.value })} /></Field>
          <Field label="Firmware version"><Input value={d.firmware_version} onChange={(e) => set({ firmware_version: e.target.value })} /></Field>
          <Field label="Serial number"><Input className="font-mono" value={d.serial_number} onChange={(e) => set({ serial_number: e.target.value })} /></Field>
          <Field label="Hardware ID"><Input value={d.hardware_id} onChange={(e) => set({ hardware_id: e.target.value })} /></Field>
          <Field label="MAC address">
            <div className="flex gap-1.5">
              <Input className="font-mono" value={d.mac} onChange={(e) => set({ mac: e.target.value })} />
              <Button variant="ghost" size="icon" onClick={() => set({ mac: randomMac() })} aria-label="New MAC"><RefreshCw /></Button>
            </div>
          </Field>
          <Field label="Endpoint UUID" hint="WS-Discovery identity (read only)" className="col-span-2"><Input className="font-mono text-xs" value={d.endpoint_uuid} disabled /></Field>
        </div>
        <SaveBar dirty={ident.dirty} saving={saveId.isPending} onReset={ident.reset} onSave={() => saveId.mutate(d, { onSuccess: ident.saved })} />
      </Section>
      <Section title="ONVIF scopes" description="One per line. type / Profile / hardware scopes are fixed for NVRs; name and location are configurable.">
        <Textarea rows={10} className="font-mono text-xs" value={scopes.draft.join("\n")} onChange={(e) => scopes.setDraft(e.target.value.split("\n").map((s) => s.trim()).filter(Boolean))} />
        <SaveBar dirty={scopes.dirty} saving={saveScopes.isPending} onReset={scopes.reset} onSave={() => saveScopes.mutate(scopes.draft!, { onSuccess: scopes.saved })} />
      </Section>
    </div>
  )
}
