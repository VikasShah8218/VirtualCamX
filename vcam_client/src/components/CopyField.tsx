import { Check, Copy } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // http:// pages on another host have no Clipboard API: fall back to a hidden textarea
    const ta = document.createElement("textarea")
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand("copy")
    ta.remove()
  }
}

/** Monospace value with a one-click copy button (testers paste ONVIF/RTSP URLs into NVRs all day). */
export function CopyField({ label, value, className }: { label?: string; value: string; className?: string }) {
  const [done, setDone] = useState(false)
  const copy = async () => {
    await copyText(value)
    setDone(true)
    toast.success("Copied", { description: value, duration: 1500 })
    setTimeout(() => setDone(false), 1200)
  }
  return (
    <div className={cn("flex min-w-0 items-center gap-2", className)}>
      {label && <span className="w-20 shrink-0 text-xs text-muted-foreground">{label}</span>}
      <code className="min-w-0 flex-1 truncate rounded-md bg-muted px-2 py-1 font-mono text-xs" title={value}>{value}</code>
      <Button variant="ghost" size="icon-sm" onClick={copy} aria-label={`Copy ${label ?? "value"}`}>
        {done ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
      </Button>
    </div>
  )
}

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  return (
    <Button variant="ghost" size="xs" onClick={() => copyText(value).then(() => toast.success("Copied", { description: value, duration: 1500 }))}>
      <Copy /> {label}
    </Button>
  )
}
