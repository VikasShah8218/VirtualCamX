import { useState } from "react"
import { useChangePassword } from "@/api/queries"
import { Field } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

/** Also shown right after the first login with the default password (must_change_password). */
export function ChangePasswordDialog({ open, onDone, forced, initialOld = "" }: { open: boolean; onDone: () => void; forced?: boolean; initialOld?: string }) {
  const change = useChangePassword()
  const [oldPw, setOldPw] = useState(initialOld)
  const [pw, setPw] = useState("")
  const [pw2, setPw2] = useState("")
  const mismatch = pw2.length > 0 && pw !== pw2
  const valid = pw.length >= 6 && pw === pw2 && (oldPw || initialOld)

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !forced && onDone()}>
      <DialogContent showCloseButton={!forced} onInteractOutside={(e) => forced && e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>{forced ? "Set a new password" : "Change password"}</DialogTitle>
          <DialogDescription>{forced ? "You signed in with the default password. Choose a new one to continue." : "At least 6 characters."}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {!forced && <Field label="Current password"><Input type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} /></Field>}
          <Field label="New password"><Input type="password" autoFocus value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
          <Field label="Repeat new password" hint={mismatch ? "Passwords do not match" : undefined}>
            <Input type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} />
          </Field>
        </div>
        <DialogFooter>
          {!forced && <Button variant="ghost" onClick={onDone}>Cancel</Button>}
          <Button
            disabled={!valid || change.isPending}
            onClick={() => change.mutate({ old_password: forced ? initialOld : oldPw, new_password: pw }, { onSuccess: onDone })}
          >
            Save password
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
