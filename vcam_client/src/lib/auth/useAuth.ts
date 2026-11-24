import { useSyncExternalStore } from "react"
import { getToken, onSessionChange, setToken } from "./session"

export function useAuth() {
  const token = useSyncExternalStore(onSessionChange, getToken)
  return { token, signedIn: !!token, logout: () => setToken(null) }
}
