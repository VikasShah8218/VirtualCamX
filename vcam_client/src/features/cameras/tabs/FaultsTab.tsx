import { X } from "lucide-react"
import { useApplyFault, useClearFault, useFaultTypes } from "@/api/queries"
import type { Camera } from "@/api/types"
import { Section } from "@/components/common"
import { Button } from "@/components/ui/button"
import { FaultForm } from "@/features/faults/FaultForm"
import { Countdown } from "@/features/faults/Countdown"

export function FaultsTab({ camera: c }: { camera: Camera }) {
  const apply = useApplyFault()
  const clear = useClearFault()
  const types = useFaultTypes()
  return (
    <div className="space-y-4">
      <Section
        title="Active faults"
        actions={c.faults.length > 1 && <Button size="xs" variant="outline" onClick={() => clear.mutate({ id: c.id, type: "all" })}>Clear all</Button>}
      >
        {c.faults.length === 0 ? (
          <div className="py-3 text-sm text-muted-foreground">No faults. The camera behaves normally.</div>
        ) : (
          <div className="space-y-2">
            {c.faults.map((f) => (
              <div key={f.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-status-fault/40 bg-status-fault/10 px-3 py-2 text-sm">
                <span className="font-medium">{types.data?.[f.type]?.label ?? f.type}</span>
                <span className="font-mono text-xs text-muted-foreground">{Object.entries(f.params).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" ")}</span>
                <span className="ml-auto text-xs">{f.expires_at ? <>clears in <Countdown until={f.expires_at} /></> : "until cleared"}</span>
                <Button size="icon-xs" variant="ghost" aria-label="Clear" onClick={() => clear.mutate({ id: c.id, type: f.type })}><X /></Button>
              </div>
            ))}
          </div>
        )}
      </Section>
      <Section title="Inject a fault" description="Simulate real-world camera problems and watch how the NVR reacts.">
        <FaultForm busy={apply.isPending} onApply={(f) => apply.mutate({ id: c.id, ...f })} />
      </Section>
    </div>
  )
}
