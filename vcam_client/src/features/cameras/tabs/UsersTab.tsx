import { KeyRound, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { useAddCameraUser, useCameraUsers, useDeleteCameraUser, useUpdateCameraUser } from "@/api/queries"
import type { Camera } from "@/api/types"
import { Field, Section } from "@/components/common"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type Level = "Administrator" | "Operator" | "User"

export function UsersTab({ camera: c }: { camera: Camera }) {
  const users = useCameraUsers(c.id)
  const add = useAddCameraUser(c.id)
  const update = useUpdateCameraUser(c.id)
  const del = useDeleteCameraUser(c.id)
  const [dialog, setDialog] = useState<null | { mode: "add" } | { mode: "edit"; username: string; level: Level }>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [level, setLevel] = useState<Level>("User")

  const open = (d: typeof dialog) => {
    setDialog(d)
    setUsername(d?.mode === "edit" ? d.username : "")
    setLevel(d?.mode === "edit" ? d.level : "User")
    setPassword("")
  }

  return (
    <Section
      title="Camera users"
      description="Used by NVRs for ONVIF (WS-Security / Digest), RTSP and snapshots, and for the camera web page. Same list ONVIF GetUsers returns."
      actions={<Button size="sm" onClick={() => open({ mode: "add" })}><Plus /> Add user</Button>}
    >
      <Table>
        <TableHeader><TableRow><TableHead>Username</TableHead><TableHead>Level</TableHead><TableHead className="w-24" /></TableRow></TableHeader>
        <TableBody>
          {(users.data ?? []).map((u) => (
            <TableRow key={u.username}>
              <TableCell className="font-mono">{u.username}</TableCell>
              <TableCell>{u.level}</TableCell>
              <TableCell className="text-right">
                <Button variant="ghost" size="icon-sm" aria-label="Change" onClick={() => open({ mode: "edit", username: u.username, level: u.level as Level })}><KeyRound /></Button>
                <Button variant="ghost" size="icon-sm" aria-label="Delete" onClick={() => setDeleting(u.username)}><Trash2 /></Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{dialog?.mode === "edit" ? `Change ${dialog.username}` : "Add camera user"}</DialogTitle>
            <DialogDescription>RTSP access changes right away; live streams keep running.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            {dialog?.mode === "add" && <Field label="Username"><Input autoFocus value={username} onChange={(e) => setUsername(e.target.value)} /></Field>}
            <Field label={dialog?.mode === "edit" ? "New password (empty = keep)" : "Password"}><Input value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
            <Field label="Level" hint="Administrator: everything · Operator: + PTZ, relays, image · User: view only">
              <Select value={level} onValueChange={(v) => setLevel(v as Level)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{(["Administrator", "Operator", "User"] as const).map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialog(null)}>Cancel</Button>
            <Button
              disabled={add.isPending || update.isPending || (dialog?.mode === "add" && (!username || !password))}
              onClick={() =>
                dialog?.mode === "add"
                  ? add.mutate({ username, password, level }, { onSuccess: () => setDialog(null) })
                  : update.mutate({ username, password: password || null, level }, { onSuccess: () => setDialog(null) })
              }
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ConfirmDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)} title={`Delete user ${deleting}?`} description="NVRs using this login will get 'Not authorized'." confirmLabel="Delete" onConfirm={() => deleting && del.mutate(deleting)} />
    </Section>
  )
}
