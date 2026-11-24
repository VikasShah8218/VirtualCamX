import { Camera as CameraIcon, CornerDownLeft } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router"
import { useCameras } from "@/api/queries"
import { StatusBadge } from "@/components/StatusBadge"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { NAV } from "./nav"

interface Item {
  key: string
  label: string
  hint: string
  to: string
  icon: React.ReactNode
  status?: string
}

/** Ctrl+K: jump to a camera (by name, number or port) or a page. */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const navigate = useNavigate()
  const cameras = useCameras()
  const [q, setQ] = useState("")
  const [active, setActive] = useState(0)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        onOpenChange(true)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onOpenChange])

  const items = useMemo<Item[]>(() => {
    const ql = q.trim().toLowerCase()
    const pages: Item[] = NAV.map((n) => ({ key: n.to, label: n.label, hint: "Page", to: n.to, icon: <n.icon className="size-4" /> }))
    const cams: Item[] = (cameras.data ?? []).map((c) => ({
      key: `c${c.id}`,
      label: c.name,
      hint: `#${String(c.number).padStart(3, "0")} · ${c.ip}:${c.http_port}`,
      to: `/cameras/${c.id}`,
      icon: <CameraIcon className="size-4" />,
      status: c.status,
    }))
    const all = [...cams, ...pages]
    return (ql ? all.filter((i) => `${i.label} ${i.hint}`.toLowerCase().includes(ql)) : all).slice(0, 30)
  }, [q, cameras.data])

  const go = (i: Item | undefined) => {
    if (!i) return
    onOpenChange(false)
    setQ("")
    navigate(i.to)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setQ("") }}>
      <DialogContent className="top-[20%] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-lg" showCloseButton={false}>
        <DialogTitle className="sr-only">Search</DialogTitle>
        <Input
          autoFocus
          placeholder="Camera name, number, port or page…"
          className="h-12 rounded-none border-0 border-b px-4 focus-visible:ring-0"
          value={q}
          onChange={(e) => { setQ(e.target.value); setActive(0) }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)) }
            if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
            if (e.key === "Enter") go(items[active])
          }}
        />
        <div className="max-h-80 overflow-y-auto p-1.5">
          {items.length === 0 && <div className="px-3 py-6 text-center text-sm text-muted-foreground">Nothing found</div>}
          {items.map((i, idx) => (
            <button
              key={i.key}
              type="button"
              onMouseEnter={() => setActive(idx)}
              onClick={() => go(i)}
              className={cn("flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm", idx === active ? "bg-accent text-accent-foreground" : "text-foreground/90")}
            >
              <span className="text-muted-foreground">{i.icon}</span>
              <span className="flex-1 truncate">{i.label}</span>
              {i.status && <StatusBadge status={i.status} compact />}
              <span className="font-mono text-xs text-muted-foreground">{i.hint}</span>
              {idx === active && <CornerDownLeft className="size-3.5 text-muted-foreground" />}
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
