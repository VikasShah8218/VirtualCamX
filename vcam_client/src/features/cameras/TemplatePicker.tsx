import { Move3d } from "lucide-react"
import { useTemplates } from "@/api/queries"
import { cn } from "@/lib/utils"

/** Camera model cards (built-in + user templates). */
export function TemplatePicker({ value, onChange }: { value: string; onChange: (key: string) => void }) {
  const templates = useTemplates()
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {(templates.data ?? []).map((t) => {
        const [w, h] = t.native
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            className={cn("rounded-lg border p-2.5 text-left transition-colors", value === t.key ? "border-primary bg-primary/10" : "hover:bg-muted")}
          >
            <div className="flex items-center gap-1.5 text-sm font-medium">
              {t.name}
              {t.ptz && <Move3d className="size-3.5 text-primary" aria-label="PTZ" />}
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">{t.model} · {w}×{h} · {String(t.main[0])}</div>
            {!t.builtin && <div className="mt-1 text-[10px] text-primary">custom</div>}
          </button>
        )
      })}
    </div>
  )
}
