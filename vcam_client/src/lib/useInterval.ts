import { useEffect, useRef } from "react"

export function useInterval(fn: () => void, ms: number | null) {
  const ref = useRef(fn)
  useEffect(() => {
    ref.current = fn
  }, [fn])
  useEffect(() => {
    if (ms == null) return
    const t = setInterval(() => ref.current(), ms)
    return () => clearInterval(t)
  }, [ms])
}
