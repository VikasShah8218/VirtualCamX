import { useState } from "react"
import { fmtDuration } from "@/lib/format"
import { useInterval } from "@/lib/useInterval"

/** Live "4m 12s" until a timestamp. */
export function Countdown({ until }: { until: string }) {
  const [now, setNow] = useState(() => Date.now())
  useInterval(() => setNow(Date.now()), 1000)
  const left = Math.max(0, (new Date(until).getTime() - now) / 1000)
  return <span className="tabular-nums">{fmtDuration(left)}</span>
}
