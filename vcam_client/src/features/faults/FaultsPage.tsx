import { X } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router"
import { useBulkClearFaults, useBulkFault, useCameras, useClearFault, useFaultTypes } from "@/api/queries"
import { PageHeader, Section } from "@/components/common"
import { StatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Countdown } from "./Countdown"
import { FaultForm } from "./FaultForm"

export function FaultsPage() {
  const cameras = useCameras()
  const types = useFaultTypes()
  const bulk = useBulkFault()
  const clear = useClearFault()
  const clearAll = useBulkClearFaults()
  const [ids, setIds] = useState<Set<number>>(new Set())
  const list = cameras.data ?? []
  const active = useMemo(() => list.flatMap((c) => c.faults.map((f) => ({ c, f }))), [list])

  return (
    <>
      <PageHeader title="Fault injection" description="Make cameras misbehave on purpose and check how the NVR copes." />
      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Section title="Cameras" description={`${ids.size} selected`} actions={<Button size="xs" variant="ghost" onClick={() => setIds(ids.size ? new Set() : new Set(list.map((c) => c.id)))}>{ids.size ? "None" : "All"}</Button>}>
          <div className="max-h-[60vh] space-y-1 overflow-y-auto">
            {list.map((c) => (
              <label key={c.id} className="flex items-center gap-2 rounded px-1 py-1 text-sm hover:bg-muted/50">
                <Checkbox checked={ids.has(c.id)} onCheckedChange={(v) => setIds((s) => { const n = new Set(s); if (v) n.add(c.id); else n.delete(c.id); return n })} />
                <span className="flex-1 truncate">{c.name}</span>
                <StatusBadge status={c.status} compact />
              </label>
            ))}
          </div>
        </Section>
        <div className="space-y-4">
          <Section title="Inject">
            <FaultForm busy={bulk.isPending} applyLabel={`Apply to ${ids.size} camera(s)`} onApply={(f) => ids.size && bulk.mutate({ ids: [...ids], ...f })} />
          </Section>
          <Section
            title={`Active faults (${active.length})`}
            actions={active.length > 0 && <Button size="xs" variant="outline" onClick={() => clearAll.mutate([...new Set(active.map((a) => a.c.id))])}>Clear all</Button>}
          >
            {active.length === 0 ? (
              <div className="py-3 text-sm text-muted-foreground">No active faults.</div>
            ) : (
              <div className="divide-y">
                {active.map(({ c, f }) => (
                  <div key={f.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                    <Link to={`/cameras/${c.id}/faults`} className="w-36 truncate font-medium hover:underline">{c.name}</Link>
                    <span className="rounded bg-status-fault/15 px-1.5 py-0.5 text-xs text-status-fault">{types.data?.[f.type]?.label ?? f.type}</span>
                    <span className="flex-1 truncate font-mono text-xs text-muted-foreground">{Object.entries(f.params).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" ")}</span>
                    <span className="text-xs">{f.expires_at ? <Countdown until={f.expires_at} /> : "until cleared"}</span>
                    <Button size="icon-xs" variant="ghost" aria-label="Clear" onClick={() => clear.mutate({ id: c.id, type: f.type })}><X /></Button>
                  </div>
                ))}
              </div>
            )}
          </Section>
        </div>
      </div>
    </>
  )
}
