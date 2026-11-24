import { useState, type ReactNode } from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Input } from "@/components/ui/input"

/** Confirmation for destructive actions. `typeToConfirm` asks the user to type a value (big bulk deletes). */
export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = "Confirm", destructive = true, typeToConfirm, onConfirm }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  confirmLabel?: string
  destructive?: boolean
  typeToConfirm?: string
  onConfirm: () => void
}) {
  const [typed, setTyped] = useState("")
  const ok = !typeToConfirm || typed.trim() === typeToConfirm
  return (
    <AlertDialog open={open} onOpenChange={(o) => { setTyped(""); onOpenChange(o) }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        {typeToConfirm && (
          <div className="space-y-1.5 text-sm">
            <div className="text-muted-foreground">Type <b className="text-foreground">{typeToConfirm}</b> to confirm.</div>
            <Input autoFocus value={typed} onChange={(e) => setTyped(e.target.value)} />
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={!ok}
            className={destructive ? "bg-destructive text-background hover:bg-destructive/90" : undefined}
            onClick={onConfirm}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
