import { useEffect, useRef, useState } from "react"

/**
 * Local editable copy of a server value for forms with a Save button.
 * The draft follows the server value until the user edits it; after a save (or when another
 * client, e.g. an NVR over ONVIF, changes the value) it re-syncs when not dirty.
 */
export function useDraft<T>(server: T | undefined) {
  const [draft, setDraftState] = useState<T | undefined>(server)
  const dirtyRef = useRef(false)
  const [dirty, setDirty] = useState(false)
  const serverKey = JSON.stringify(server ?? null)

  useEffect(() => {
    if (!dirtyRef.current) setDraftState(server)
    // serverKey is the stable identity of `server`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverKey])

  const setDraft = (next: T | ((prev: T) => T)) => {
    dirtyRef.current = true
    setDirty(true)
    setDraftState((prev) => (typeof next === "function" ? (next as (p: T) => T)(prev as T) : next))
  }
  const reset = () => {
    dirtyRef.current = false
    setDirty(false)
    setDraftState(server)
  }
  /** Call after a successful save: the next server value replaces the draft. */
  const saved = () => {
    dirtyRef.current = false
    setDirty(false)
  }
  return { draft, setDraft, dirty, reset, saved }
}
