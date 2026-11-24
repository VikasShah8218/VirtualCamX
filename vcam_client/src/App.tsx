import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query"
import { lazy, Suspense, type ReactNode } from "react"
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router"
import { Loading } from "@/components/common"
import { AppLayout } from "@/components/layout/AppLayout"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ApiError } from "@/api/client"
import { useAuth } from "@/lib/auth/useAuth"
import { useRealtime } from "@/lib/realtime"

// Pages are lazy-loaded: each is its own small file in the build.
const page = <T extends Record<string, unknown>>(load: () => Promise<T>, name: keyof T) =>
  lazy(() => load().then((m) => ({ default: m[name] as React.ComponentType })))

const LoginPage = page(() => import("@/features/auth/LoginPage"), "LoginPage")
const DashboardPage = page(() => import("@/features/dashboard/DashboardPage"), "DashboardPage")
const CamerasPage = page(() => import("@/features/cameras/CamerasPage"), "CamerasPage")
const CameraDetailPage = page(() => import("@/features/cameras/CameraDetailPage"), "CameraDetailPage")
const LiveWallPage = page(() => import("@/features/live/LiveWallPage"), "LiveWallPage")
const MediaPage = page(() => import("@/features/media/MediaPage"), "MediaPage")
const TemplatesPage = page(() => import("@/features/templates/TemplatesPage"), "TemplatesPage")
const EventsPage = page(() => import("@/features/events/EventsPage"), "EventsPage")
const FaultsPage = page(() => import("@/features/faults/FaultsPage"), "FaultsPage")
const InspectorPage = page(() => import("@/features/inspector/InspectorPage"), "InspectorPage")
const SettingsPage = page(() => import("@/features/settings/SettingsPage"), "SettingsPage")

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      // A 401/403/404 will not fix itself by retrying
      retry: (count, err) => !(err instanceof ApiError && [401, 403, 404, 422].includes(err.status)) && count < 2,
    },
  },
})

function Realtime() {
  useRealtime(useQueryClient())
  return null
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { signedIn } = useAuth()
  const location = useLocation()
  if (!signedIn) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  return <>{children}</>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        <BrowserRouter>
          <Realtime />
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
                <Route index element={<DashboardPage />} />
                <Route path="cameras" element={<CamerasPage />} />
                <Route path="cameras/:id" element={<CameraDetailPage />} />
                <Route path="cameras/:id/:tab" element={<CameraDetailPage />} />
                <Route path="live" element={<LiveWallPage />} />
                <Route path="media" element={<MediaPage />} />
                <Route path="templates" element={<TemplatesPage />} />
                <Route path="events" element={<EventsPage />} />
                <Route path="faults" element={<FaultsPage />} />
                <Route path="inspector" element={<InspectorPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
        <Toaster position="bottom-right" richColors closeButton />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
