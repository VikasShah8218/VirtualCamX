/**
 * Manager sign-in session: the JWT from POST /api/v1/auth/login.
 * Kept in memory and (with "remember me") in localStorage. A 401 anywhere ends the session.
 */
const KEY = "vcamx.token"

type Listener = () => void
const listeners = new Set<Listener>()

let token: string | null = (() => {
  try {
    return localStorage.getItem(KEY) ?? sessionStorage.getItem(KEY)
  } catch {
    return null
  }
})()

export function getToken(): string | null {
  return token
}

export function setToken(value: string | null, remember = true) {
  token = value
  try {
    localStorage.removeItem(KEY)
    sessionStorage.removeItem(KEY)
    if (value) (remember ? localStorage : sessionStorage).setItem(KEY, value)
  } catch {
    // storage blocked: the session lives only in memory
  }
  listeners.forEach((l) => l())
}

export function onSessionChange(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Called by the API client on any 401: drop the token; RequireAuth then shows the login page. */
export function handleUnauthorized() {
  if (token) setToken(null)
}
