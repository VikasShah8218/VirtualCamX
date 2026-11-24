import createClient from "openapi-fetch"
import { getToken, handleUnauthorized } from "@/lib/auth/session"
import type { paths as CameraPaths } from "./camera"
import type { paths as ManagerPaths } from "./manager"

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** FastAPI errors: {"detail": "text"} or {"detail": [{"loc", "msg"}, ...]} (validation). */
export function errorMessage(error: unknown, status: number): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const where = (d.loc ?? []).filter((p) => p !== "body").join(".")
        return where ? `${where}: ${d.msg ?? ""}` : (d.msg ?? "")
      })
      .join("; ")
  }
  return status ? `Request failed (HTTP ${status})` : "Server unreachable"
}

/** Resolve an openapi-fetch call to its data, or throw ApiError carrying the server's message. */
export async function unwrap<T>(call: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let result
  try {
    result = await call
  } catch {
    throw new ApiError(0, "Server unreachable")
  }
  const { data, error, response } = result
  if (error !== undefined || !response.ok) throw new ApiError(response.status, errorMessage(error, response.status))
  return data as T
}

/** Manager API (/api/v1). Same origin: served by vcam_server on :9000, or proxied by Vite in dev. */
export const api = createClient<ManagerPaths>({ baseUrl: "" })
api.use({
  onRequest({ request }) {
    const t = getToken()
    if (t) request.headers.set("Authorization", `Bearer ${t}`)
    return request
  },
  onResponse({ response, request }) {
    if (response.status === 401 && !request.url.endsWith("/auth/login")) handleUnauthorized()
    return response
  },
})

/** Camera web API (/api/cam/v1) of the camera that served this page. Auth = per-camera session cookie. */
export const camApi = createClient<CameraPaths>({ baseUrl: "", credentials: "same-origin" })

// ---- URLs the browser opens itself (img, links): they cannot send the Authorization header ----

export function snapshotUrl(cameraId: number, bust?: number) {
  const q = new URLSearchParams({ token: getToken() ?? "" })
  if (bust) q.set("t", String(bust))
  return `/api/v1/cameras/${cameraId}/snapshot?${q}`
}

export const managerWhepUrl = (cameraId: number, stream: string) => `/api/v1/cameras/${cameraId}/live/${stream}/whep`
export const cameraWhepUrl = (stream: string) => `/api/cam/v1/live/${stream}/whep`

export function wsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:"
  return `${proto}//${location.host}/api/v1/ws?token=${encodeURIComponent(getToken() ?? "")}`
}

/** Plain JSON call for the few endpoints whose body OpenAPI cannot describe (PUT /state/{section}). */
export async function requestJson<T>(method: string, url: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  const t = getToken()
  if (t && url.startsWith("/api/v1")) headers.Authorization = `Bearer ${t}`
  let res: Response
  try {
    res = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), credentials: "same-origin" })
  } catch {
    throw new ApiError(0, "Server unreachable")
  }
  if (res.status === 401 && url.startsWith("/api/v1")) handleUnauthorized()
  let data: unknown
  try {
    data = await res.json()
  } catch {
    data = undefined
  }
  if (!res.ok) throw new ApiError(res.status, errorMessage(data, res.status))
  return data as T
}
