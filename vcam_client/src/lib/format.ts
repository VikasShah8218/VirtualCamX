import { formatDistanceToNowStrict } from "date-fns"

export function fmtKbps(kbps: number | null | undefined): string {
  if (kbps == null || !Number.isFinite(kbps)) return "—"
  if (kbps >= 1000) return `${(kbps / 1000).toFixed(kbps >= 10000 ? 0 : 1)} Mbps`
  return `${Math.round(kbps)} kbps`
}

export function fmtBytes(n: number | null | undefined): string {
  if (n == null) return "—"
  const units = ["B", "KB", "MB", "GB", "TB"]
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "—"
  const s = Math.round(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h) return `${h}h ${m}m`
  if (m) return `${m}m ${sec}s`
  return `${sec}s`
}

export function fmtAgo(value: string | number | Date | null | undefined): string {
  if (value == null) return "—"
  const d = typeof value === "number" ? new Date(value < 1e12 ? value * 1000 : value) : new Date(value)
  if (Number.isNaN(d.getTime())) return "—"
  return `${formatDistanceToNowStrict(d)} ago`
}

export function fmtTime(value: string | number | Date): string {
  const d = typeof value === "number" ? new Date(value < 1e12 ? value * 1000 : value) : new Date(value)
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

export const fmtRes = (w?: number | null, h?: number | null) => (w && h ? `${w}×${h}` : "—")

/** "Lab-{n:03d}" -> "Lab-007" (same rule as the backend's str.format with n). */
export function renderNamePattern(pattern: string, n: number): string {
  return pattern.replace(/\{n(?::(0?)(\d+)d)?\}/g, (_, zero: string, width: string) =>
    width ? String(n).padStart(Number(width), zero ? "0" : " ") : String(n),
  )
}

/** Topic "tns1:VideoSource/MotionAlarm" -> "Motion alarm" for humans. */
export function topicLabel(topic: string): string {
  const t = topic.replace(/^tns1:/, "")
  const map: Record<string, string> = {
    "VideoSource/MotionAlarm": "Motion alarm",
    "RuleEngine/CellMotionDetector/Motion": "Cell motion",
    "VideoSource/GlobalSceneChange/ImagingService": "Tamper",
    "Device/Trigger/DigitalInput": "Digital input",
    "Device/Trigger/Relay": "Relay",
    "VideoSource/SignalLoss": "Video loss",
  }
  return map[t] ?? t
}

/** The boolean-ish value of an ONVIF event message: State / IsMotion / LogicalState. */
export function eventActive(data: Record<string, unknown>): boolean {
  const v = String(data.State ?? data.IsMotion ?? data.LogicalState ?? "")
  return v === "true" || v === "active"
}
