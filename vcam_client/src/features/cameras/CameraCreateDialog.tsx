import { ChevronDown } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router"
import { useCreateCamera } from "@/api/queries"
import type { SourceSpec } from "@/api/types"
import { Field } from "@/components/common"
import { SourcePicker, StreamModePicker } from "@/components/SourcePicker"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { makeSource } from "@/lib/source"
import { TemplatePicker } from "./TemplatePicker"

export function CameraCreateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const create = useCreateCamera()
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [template, setTemplate] = useState("bullet_2mp")
  const [source, setSource] = useState<SourceSpec>(makeSource({ type: "test_pattern" }))
  const [mode, setMode] = useState<"encode" | "passthrough">("encode")
  const [advanced, setAdvanced] = useState(false)
  const [port, setPort] = useState("")
  const [user, setUser] = useState("")
  const [password, setPassword] = useState("")

  const submit = (openAfter: boolean) =>
    create.mutate(
      {
        name: name.trim() || null,
        template_key: template,
        source,
        stream_mode: source.type === "file" ? mode : "encode",
        http_port: port ? Number(port) : null,
        username: user || null,
        password: password || null,
        enabled: true,
      },
      {
        onSuccess: (cam) => {
          onOpenChange(false)
          setName("")
          if (openAfter) navigate(`/cameras/${cam.id}`)
        },
      },
    )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New virtual camera</DialogTitle>
          <DialogDescription>It starts right away and answers ONVIF, RTSP and WS-Discovery like a real IP camera.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <Field label="Name" hint="Leave empty for an automatic name (VCam-004).">
            <Input autoFocus placeholder="Gate-1" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Camera model">
            <TemplatePicker value={template} onChange={setTemplate} />
          </Field>
          <Field label="Video source">
            <SourcePicker value={source} onChange={setSource} />
          </Field>
          {source.type === "file" && (
            <Field label="Stream mode">
              <StreamModePicker value={mode} onChange={setMode} />
            </Field>
          )}
          <button type="button" className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground" onClick={() => setAdvanced((a) => !a)}>
            <ChevronDown className={advanced ? "size-3.5 rotate-180" : "size-3.5"} /> Port and login
          </button>
          {advanced && (
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="HTTP/ONVIF port" hint="Empty = next free port"><Input type="number" value={port} onChange={(e) => setPort(e.target.value)} /></Field>
              <Field label="Admin user" hint="Default: admin"><Input value={user} onChange={(e) => setUser(e.target.value)} /></Field>
              <Field label="Password" hint="Default: admin123"><Input value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="secondary" disabled={create.isPending} onClick={() => submit(false)}>Create</Button>
          <Button disabled={create.isPending} onClick={() => submit(true)}>Create and open</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
