import { Loader2, Save, Undo2 } from "lucide-react"
import { Button } from "@/components/ui/button"

/** Save / discard buttons for a form; only visible while there are unsaved changes. */
export function SaveBar({ dirty, saving, onSave, onReset, note }: { dirty: boolean; saving?: boolean; onSave: () => void; onReset: () => void; note?: string }) {
  if (!dirty) return null
  return (
    <div className="sticky bottom-2 z-10 mt-4 flex items-center justify-end gap-2 rounded-lg border bg-popover px-3 py-2 shadow-lg">
      <span className="mr-auto text-xs text-muted-foreground">{note ?? "Unsaved changes"}</span>
      <Button variant="ghost" size="sm" onClick={onReset} disabled={saving}><Undo2 /> Discard</Button>
      <Button size="sm" onClick={onSave} disabled={saving}>{saving ? <Loader2 className="animate-spin" /> : <Save />} Save</Button>
    </div>
  )
}
