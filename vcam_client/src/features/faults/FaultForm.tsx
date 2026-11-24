import { ShieldAlert } from "lucide-react"
import { useEffect, useState } from "react"
import { useFaultTypes } from "@/api/queries"
import { Field } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"

export interface FaultRequest {
  type: string
  params: Record<string, unknown>
  duration_s: number | null
}

/** Pick a fault type, fill its parameters (from GET /faults/types) and a duration. */
export function FaultForm({ onApply, busy, applyLabel = "Apply fault" }: { onApply: (f: FaultRequest) => void; busy?: boolean; applyLabel?: string }) {
  const types = useFaultTypes()
  const [type, setType] = useState("offline")
  const [params, setParams] = useState<Record<string, unknown>>({})
  const [duration, setDuration] = useState("60")
  const def = types.data?.[type]

  useEffect(() => {
    if (def) setParams(def.params)
  }, [type, def])

  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {Object.entries(types.data ?? {}).map(([k, t]) => (
          <button key={k} type="button" onClick={() => setType(k)} className={cn("rounded-lg border p-2.5 text-left transition-colors", type === k ? "border-status-fault bg-status-fault/10" : "hover:bg-muted")}>
            <div className="text-sm font-medium">{t.label}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">{t.desc}</div>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        {Object.entries(params).map(([k, v]) => (
          <Field key={k} label={k.replace(/_/g, " ")}>
            {Array.isArray(v) ? (
              <Input className="w-64 font-mono text-xs" value={(v as string[]).join(", ")} onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }))} />
            ) : (
              <Input type="number" className="w-32" value={String(v)} onChange={(e) => setParams((p) => ({ ...p, [k]: Number(e.target.value) }))} />
            )}
          </Field>
        ))}
        {type !== "reboot" && !(type === "stream_drop" && !Number(params.repeat_every_s)) && (
          <Field label="Duration">
            <Select value={duration} onValueChange={setDuration}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                {["30", "60", "300", "900", "3600"].map((s) => <SelectItem key={s} value={s}>{Number(s) >= 60 ? `${Number(s) / 60} min` : `${s} s`}</SelectItem>)}
                <SelectItem value="0">Until cleared</SelectItem>
              </SelectContent>
            </Select>
          </Field>
        )}
        <Button disabled={busy} onClick={() => onApply({ type, params, duration_s: Number(duration) || null })} className="bg-status-fault text-background hover:bg-status-fault/90">
          <ShieldAlert /> {applyLabel}
        </Button>
      </div>
    </div>
  )
}
