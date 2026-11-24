import { cn } from "@/lib/utils"

/** Camera status colors come from theme.css (--status-*), so a theme change restyles every badge. */
const STYLES: Record<string, { dot: string; text: string; label: string; pulse?: boolean }> = {
  running: { dot: "bg-status-running", text: "text-status-running", label: "Running" },
  starting: { dot: "bg-status-starting", text: "text-status-starting", label: "Starting", pulse: true },
  rebooting: { dot: "bg-status-rebooting", text: "text-status-rebooting", label: "Rebooting", pulse: true },
  stopping: { dot: "bg-status-starting", text: "text-status-starting", label: "Stopping", pulse: true },
  offline: { dot: "bg-status-offline", text: "text-status-offline", label: "Offline" },
  error: { dot: "bg-status-error", text: "text-status-error", label: "Error" },
  stopped: { dot: "bg-status-stopped", text: "text-status-stopped", label: "Stopped" },
}

export function statusStyle(status: string) {
  return STYLES[status] ?? STYLES.stopped
}

export function StatusBadge({ status, className, compact }: { status: string; className?: string; compact?: boolean }) {
  const s = statusStyle(status)
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", s.text, className)} title={s.label}>
      <span className={cn("size-2 shrink-0 rounded-full", s.dot, s.pulse && "animate-pulse")} />
      {!compact && s.label}
    </span>
  )
}

export function FaultBadge({ count }: { count: number }) {
  if (!count) return null
  return (
    <span className="rounded-full bg-status-fault/20 px-1.5 py-0.5 text-[10px] font-semibold text-status-fault" title="Active faults">
      {count} fault{count > 1 ? "s" : ""}
    </span>
  )
}
