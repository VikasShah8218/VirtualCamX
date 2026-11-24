import { Loader2, LogIn } from "lucide-react"
import { useState } from "react"
import { Navigate, useNavigate, useSearchParams } from "react-router"
import { login, useHealth } from "@/api/queries"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { setToken } from "@/lib/auth/session"
import { useAuth } from "@/lib/auth/useAuth"
import { PRODUCT_LOGO, PRODUCT_NAME } from "@/lib/branding"
import { cn } from "@/lib/utils"
import { ChangePasswordDialog } from "./ChangePasswordDialog"

export function LoginPage() {
  const { signedIn } = useAuth()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const health = useHealth()
  const [username, setUsername] = useState("admin")
  const [password, setPassword] = useState("")
  const [remember, setRemember] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mustChange, setMustChange] = useState(false)
  const next = params.get("next") || "/"

  if (signedIn && !mustChange) return <Navigate to={next} replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await login(username, password)
      setToken(r.access_token, remember)
      if (r.must_change_password) setMustChange(true)
      else navigate(next, { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const h = health.data
  const checks = h
    ? [
        { label: "FFmpeg", ok: !!h.ffmpeg?.ok },
        { label: "MediaMTX", ok: h.mediamtx.running },
        { label: "WS-Discovery", ok: h.ws_discovery.running },
      ]
    : []

  return (
    <div className="grid min-h-dvh place-items-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <img src={PRODUCT_LOGO} alt="" className="size-14" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{PRODUCT_NAME}</h1>
            <p className="text-sm text-muted-foreground">Virtual ONVIF camera farm for NVR testing</p>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-xl border bg-card p-5">
          <div className="space-y-1.5">
            <Label htmlFor="u">Username</Label>
            <Input id="u" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="p">Password</Label>
            <Input id="p" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Switch checked={remember} onCheckedChange={setRemember} size="sm" /> Remember me on this browser
          </label>
          {error && <div className="rounded-md bg-destructive/15 px-3 py-2 text-sm text-destructive">{error}</div>}
          <Button type="submit" className="w-full" size="lg" disabled={busy || !username || !password}>
            {busy ? <Loader2 className="animate-spin" /> : <LogIn />} Sign in
          </Button>
        </form>
        <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-muted-foreground">
          {health.isError && <span className="text-danger">Server unreachable</span>}
          {checks.map((c) => (
            <span key={c.label} className="inline-flex items-center gap-1.5">
              <span className={cn("size-2 rounded-full", c.ok ? "bg-success" : "bg-danger")} /> {c.label}
            </span>
          ))}
        </div>
      </div>
      <ChangePasswordDialog
        open={mustChange}
        forced
        onDone={() => { setMustChange(false); navigate(next, { replace: true }) }}
        initialOld={password}
      />
    </div>
  )
}
