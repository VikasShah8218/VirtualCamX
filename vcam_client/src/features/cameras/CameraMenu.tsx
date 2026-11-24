import { Copy, ExternalLink, MoreHorizontal, Play, RefreshCw, RotateCcw, Square, Trash2 } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router"
import { useCameraControl, useDeleteCamera } from "@/api/queries"
import type { Camera } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { copyText } from "@/components/CopyField"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { toast } from "sonner"

/** Per-camera actions (list rows, grid cards). */
export function CameraMenu({ camera, align = "end" }: { camera: Camera; align?: "start" | "end" }) {
  const control = useCameraControl()
  const del = useDeleteCamera()
  const navigate = useNavigate()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const act = (action: "start" | "stop" | "restart" | "reboot") => control.mutate({ id: camera.id, action, name: camera.name })
  const copy = (label: string, v: string) => copyText(v).then(() => toast.success(`${label} copied`, { description: v, duration: 1500 }))
  const running = camera.status === "running"

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label="Camera actions" onClick={(e) => e.stopPropagation()}>
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align={align} className="w-56" onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem onSelect={() => navigate(`/cameras/${camera.id}`)}>Open</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => window.open(camera.urls.web, "_blank")}><ExternalLink /> Camera web page</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => copy("ONVIF URL", camera.urls.onvif)}><Copy /> Copy ONVIF URL</DropdownMenuItem>
          {Object.entries(camera.urls.rtsp).map(([k, v]) => (
            <DropdownMenuItem key={k} onSelect={() => copy(`RTSP ${k}`, v)}><Copy /> Copy RTSP {k}</DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          {running ? (
            <DropdownMenuItem onSelect={() => act("stop")}><Square /> Stop</DropdownMenuItem>
          ) : (
            <DropdownMenuItem onSelect={() => act("start")}><Play /> Start</DropdownMenuItem>
          )}
          <DropdownMenuItem onSelect={() => act("restart")}><RefreshCw /> Restart</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => act("reboot")} disabled={!running}><RotateCcw /> Reboot (like a real camera)</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => setConfirmDelete(true)}><Trash2 /> Delete</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete ${camera.name}?`}
        description="The camera disappears from the network: NVRs that use it will lose it. Footage files are not touched."
        confirmLabel="Delete camera"
        onConfirm={() => del.mutate(camera)}
      />
    </>
  )
}

