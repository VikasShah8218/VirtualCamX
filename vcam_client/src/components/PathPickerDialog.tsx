import { ArrowUp, File, FileVideo, Folder, HardDrive, ImageIcon, Loader2 } from "lucide-react"
import { useEffect, useState } from "react"
import { useBrowse, useFsRoots } from "@/api/queries"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { fmtBytes } from "@/lib/format"
import { readStored, writeStored } from "@/lib/storage"
import { cn } from "@/lib/utils"

const LAST_DIR = "vcamx.lastDir"

/**
 * Browse folders on the machine running VirtualCamX (not the browser's PC) and pick a file
 * or a folder. Footage is used in place: nothing is uploaded.
 */
export function PathPickerDialog({ open, onOpenChange, onPick, mode = "file", accept = "video", title }: {
  open: boolean
  onOpenChange: (o: boolean) => void
  onPick: (path: string, files?: string[]) => void
  mode?: "file" | "folder"
  accept?: "video" | "image" | "any"
  title?: string
}) {
  const roots = useFsRoots()
  const [dir, setDir] = useState<string | null>(() => readStored(LAST_DIR, { dir: null as string | null }).dir)
  const [typed, setTyped] = useState("")
  const [showAll, setShowAll] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const browse = useBrowse(dir, showAll)

  useEffect(() => {
    if (open) setSelected(null)
  }, [open, dir])
  useEffect(() => {
    if (browse.isSuccess) writeStored(LAST_DIR, { dir: browse.data.path })
  }, [browse.isSuccess, browse.data])

  const entries = (browse.data?.entries ?? []).filter((e) => e.is_dir || accept === "any" || showAll || e.kind === accept)
  const matching = entries.filter((e) => !e.is_dir && (accept === "any" || e.kind === accept)).map((e) => e.path)

  const pickTyped = () => {
    const p = typed.trim().replace(/^"|"$/g, "")
    if (!p) return
    if (mode === "file" && /\.[a-z0-9]{2,5}$/i.test(p)) {
      onPick(p)
      onOpenChange(false)
    } else setDir(p)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title ?? (mode === "file" ? "Choose a video file" : "Choose a folder")}</DialogTitle>
          <DialogDescription>Folders on the VirtualCamX server. The file is used in place, never uploaded or copied.</DialogDescription>
        </DialogHeader>

        <div className="flex gap-2">
          <Input placeholder="Paste a path, e.g. D:\Footage\gate.mp4" value={typed} onChange={(e) => setTyped(e.target.value)} onKeyDown={(e) => e.key === "Enter" && pickTyped()} className="font-mono text-xs" />
          <Button variant="secondary" onClick={pickTyped}>Go</Button>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {(roots.data ?? []).map((r) => (
            <Button key={r.path} variant={dir?.startsWith(r.path) ? "secondary" : "ghost"} size="xs" onClick={() => setDir(r.path)}>
              <HardDrive /> {r.name}
            </Button>
          ))}
          <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
            <Switch size="sm" checked={showAll} onCheckedChange={setShowAll} /> Show all files
          </label>
        </div>

        <div className="flex items-center gap-2 rounded-md bg-muted px-2 py-1">
          <Button variant="ghost" size="icon-xs" disabled={!browse.data?.parent} onClick={() => setDir(browse.data!.parent!)} aria-label="Up">
            <ArrowUp />
          </Button>
          <code className="min-w-0 flex-1 truncate font-mono text-xs">{browse.data?.path ?? dir ?? "Pick a drive"}</code>
        </div>

        <div className="h-72 overflow-y-auto rounded-md border">
          {browse.isFetching && !browse.data && <div className="flex h-full items-center justify-center text-sm text-muted-foreground"><Loader2 className="mr-2 size-4 animate-spin" />Loading…</div>}
          {browse.isError && <div className="p-4 text-sm text-destructive">{(browse.error as Error).message}</div>}
          {!dir && <div className="p-4 text-sm text-muted-foreground">Choose a drive above or paste a path.</div>}
          {browse.data && entries.length === 0 && <div className="p-4 text-sm text-muted-foreground">No {accept === "any" ? "files" : `${accept} files`} or folders here.</div>}
          {entries.map((e) => (
            <button
              key={e.path}
              type="button"
              onClick={() => (e.is_dir ? setDir(e.path) : setSelected(e.path))}
              onDoubleClick={() => { if (!e.is_dir && mode === "file") { onPick(e.path); onOpenChange(false) } }}
              className={cn("flex w-full items-center gap-2.5 px-3 py-1.5 text-left text-sm hover:bg-accent", selected === e.path && "bg-accent text-accent-foreground")}
            >
              {e.is_dir ? <Folder className="size-4 text-primary" /> : e.kind === "video" ? <FileVideo className="size-4 text-chart-2" /> : e.kind === "image" ? <ImageIcon className="size-4 text-chart-3" /> : <File className="size-4 text-muted-foreground" />}
              <span className="min-w-0 flex-1 truncate">{e.name}</span>
              {!e.is_dir && <span className="text-xs text-muted-foreground tabular-nums">{fmtBytes(e.size_bytes)}</span>}
            </button>
          ))}
        </div>

        <DialogFooter className="items-center sm:justify-between">
          <span className="text-xs text-muted-foreground">{mode === "folder" && browse.data ? `${matching.length} ${accept} file(s) in this folder` : selected ?? ""}</span>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            {mode === "file" ? (
              <Button disabled={!selected} onClick={() => { onPick(selected!); onOpenChange(false) }}>Use this file</Button>
            ) : (
              <Button disabled={!browse.data || matching.length === 0} onClick={() => { onPick(browse.data!.path, matching); onOpenChange(false) }}>Use this folder</Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
