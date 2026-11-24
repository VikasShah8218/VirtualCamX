/**
 * React Query hooks for the Manager API. One hook per call: useXxx() reads, useXxxAction() changes.
 * Mutations show a toast and refresh the related queries. Live updates arrive over the WebSocket
 * (lib/realtime.ts), which patches these same cache keys.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query"
import { toast } from "sonner"
import { api, requestJson, unwrap } from "./client"
import type {
  BulkAction,
  BulkCreate,
  BulkSourceIn,
  Camera,
  CameraCreate,
  CameraPatch,
  CameraState,
  FaultIn,
  ScheduleIn,
  SourceSpec,
  TriggerIn,
} from "./types"

export const qk = {
  health: ["health"] as const,
  stats: ["stats"] as const,
  cameras: ["cameras"] as const,
  camera: (id: number) => ["cameras", id] as const,
  state: (id: number) => ["cameras", id, "state"] as const,
  clients: (id: number) => ["cameras", id, "clients"] as const,
  log: (id: number) => ["cameras", id, "log"] as const,
  camUsers: (id: number) => ["cameras", id, "users"] as const,
  events: (id: number) => ["cameras", id, "events"] as const,
  eventState: (id: number) => ["cameras", id, "event-state"] as const,
  schedules: ["schedules"] as const,
  faultTypes: ["fault-types"] as const,
  inspector: ["inspector"] as const,
  inspectorEntry: (id: number) => ["inspector", "entry", id] as const,
  fsRoots: ["fs", "roots"] as const,
  browse: (path: string) => ["fs", "browse", path] as const,
  media: ["media"] as const,
  jobs: ["media", "jobs"] as const,
  templates: ["templates"] as const,
  settings: ["settings"] as const,
  editable: ["settings", "editable"] as const,
  nics: ["nics"] as const,
  admins: ["admins"] as const,
  me: ["me"] as const,
}

/** Mutation with the house rules: toast on success/error and invalidate related queries. */
function useAction<TArgs, TResult>(
  fn: (args: TArgs) => Promise<TResult>,
  opts: { success?: string | ((r: TResult, a: TArgs) => string | null); invalidate?: (a: TArgs) => QueryKey[] } = {},
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (result, args) => {
      const msg = typeof opts.success === "function" ? opts.success(result, args) : opts.success
      if (msg) toast.success(msg)
      opts.invalidate?.(args).forEach((key) => qc.invalidateQueries({ queryKey: key }))
    },
    onError: (err) => toast.error(err.message),
  })
}

// ============================================================ system

export const useHealth = () =>
  useQuery({ queryKey: qk.health, queryFn: () => unwrap(api.GET("/api/v1/system/health")), refetchInterval: 15_000, retry: false })

export const useStats = () =>
  useQuery({ queryKey: qk.stats, queryFn: () => unwrap(api.GET("/api/v1/system/stats")), refetchInterval: 30_000 })

export const useServerSettings = () =>
  useQuery({ queryKey: qk.settings, queryFn: () => unwrap(api.GET("/api/v1/system/settings")) as Promise<Record<string, unknown>> })

export const useEditableSettings = () =>
  useQuery({ queryKey: qk.editable, queryFn: () => unwrap(api.GET("/api/v1/system/settings/editable")) })

export const useNics = () => useQuery({ queryKey: qk.nics, queryFn: () => unwrap(api.GET("/api/v1/system/nics")) })

export const useUpdateSettings = () =>
  useAction((changes: Record<string, unknown>) => unwrap(api.PUT("/api/v1/system/settings", { body: changes })), {
    success: "Settings saved",
    invalidate: () => [qk.settings],
  })

// ============================================================ auth / admin users

export async function login(username: string, password: string) {
  return unwrap(api.POST("/api/v1/auth/login", { body: { username, password } }))
}

export const useAdmins = () => useQuery({ queryKey: qk.admins, queryFn: () => unwrap(api.GET("/api/v1/auth/users")) })

export const useCreateAdmin = () =>
  useAction((body: { username: string; password: string }) => unwrap(api.POST("/api/v1/auth/users", { body })), {
    success: (_, a) => `Admin ${a.username} created`,
    invalidate: () => [qk.admins],
  })

export const useDeleteAdmin = () =>
  useAction((id: number) => unwrap(api.DELETE("/api/v1/auth/users/{user_id}", { params: { path: { user_id: id } } })), {
    success: "Admin deleted",
    invalidate: () => [qk.admins],
  })

export const useChangePassword = () =>
  useAction(
    (body: { old_password: string; new_password: string }) => unwrap(api.POST("/api/v1/auth/change-password", { body })),
    { success: "Password changed" },
  )

// ============================================================ cameras: reads

export const useCameras = () =>
  useQuery({
    queryKey: qk.cameras,
    queryFn: () => unwrap(api.GET("/api/v1/cameras")),
    select: (d) => d.items,
    refetchInterval: 30_000,
  })

export const useCamera = (id: number) =>
  useQuery({ queryKey: qk.camera(id), queryFn: () => unwrap(api.GET("/api/v1/cameras/{camera_id}", { params: { path: { camera_id: id } } })) })

export const useCameraState = (id: number) =>
  useQuery({
    queryKey: qk.state(id),
    queryFn: () => unwrap(api.GET("/api/v1/cameras/{camera_id}/state", { params: { path: { camera_id: id } } })) as Promise<CameraState>,
  })

export const useCameraClients = (id: number) =>
  useQuery({
    queryKey: qk.clients(id),
    queryFn: () => unwrap(api.GET("/api/v1/cameras/{camera_id}/clients", { params: { path: { camera_id: id } } })),
    refetchInterval: 5_000,
  })

export const useCameraLog = (id: number) =>
  useQuery({
    queryKey: qk.log(id),
    queryFn: () => unwrap(api.GET("/api/v1/cameras/{camera_id}/log", { params: { path: { camera_id: id } } })),
    refetchInterval: 5_000,
  })

export const useCameraUsers = (id: number) =>
  useQuery({ queryKey: qk.camUsers(id), queryFn: () => unwrap(api.GET("/api/v1/cameras/{camera_id}/users", { params: { path: { camera_id: id } } })) })

// ============================================================ cameras: changes

const camKeys = (id?: number) => (id ? [qk.cameras, qk.camera(id), qk.state(id)] : [qk.cameras])

export const useCreateCamera = () =>
  useAction((body: CameraCreate) => unwrap(api.POST("/api/v1/cameras", { body })), {
    success: (c) => `Camera ${c.name} created on port ${c.http_port}`,
    invalidate: () => [qk.cameras, qk.stats],
  })

export const useBulkCreate = () =>
  useAction((body: BulkCreate) => unwrap(api.POST("/api/v1/cameras/bulk", { body })), {
    success: (r) => `${r.created.length} cameras created`,
    invalidate: () => [qk.cameras, qk.stats],
  })

export const useBulkAction = () =>
  useAction(
    (body: { ids: number[]; action: BulkAction; params?: Record<string, unknown> }) =>
      unwrap(api.POST("/api/v1/cameras/bulk-action", { body: { params: {}, ...body } })),
    {
      success: (r, a) => {
        const results = Object.values(r.results)
        const failed = results.filter((x) => x !== "ok").length
        return failed ? null : `${a.action}: ${results.length} camera(s) done`
      },
      invalidate: () => [qk.cameras, qk.stats],
    },
  )

export const useBulkSource = () =>
  useAction(
    (body: BulkSourceIn) => unwrap(api.PUT("/api/v1/cameras/bulk-source", { body })),
    { success: (r) => `Source changed on ${Object.values(r.results).filter((x) => x === "ok").length} camera(s)`, invalidate: () => [qk.cameras] },
  )

export const usePatchCamera = (id: number) =>
  useAction((body: CameraPatch) => unwrap(api.PATCH("/api/v1/cameras/{camera_id}", { params: { path: { camera_id: id } }, body })), {
    success: "Camera updated",
    invalidate: () => camKeys(id),
  })

export const useDeleteCamera = () =>
  useAction((c: Pick<Camera, "id" | "name">) => unwrap(api.DELETE("/api/v1/cameras/{camera_id}", { params: { path: { camera_id: c.id } } })), {
    success: (_, c) => `${c.name} deleted`,
    invalidate: () => [qk.cameras, qk.stats],
  })

export type ControlAction = "start" | "stop" | "restart" | "reboot" | "factory-reset"

export const useCameraControl = () =>
  useAction(
    ({ id, action }: { id: number; action: ControlAction; name?: string }) => {
      const path = { params: { path: { camera_id: id } } }
      switch (action) {
        case "start": return unwrap(api.POST("/api/v1/cameras/{camera_id}/start", path))
        case "stop": return unwrap(api.POST("/api/v1/cameras/{camera_id}/stop", path))
        case "restart": return unwrap(api.POST("/api/v1/cameras/{camera_id}/restart", path))
        case "reboot": return unwrap(api.POST("/api/v1/cameras/{camera_id}/reboot", path))
        case "factory-reset": return unwrap(api.POST("/api/v1/cameras/{camera_id}/factory-reset", path))
      }
    },
    { success: (_, a) => `${a.name ?? "Camera"}: ${a.action.replace("-", " ")}`, invalidate: (a) => camKeys(a.id) },
  )

export const useSetSource = (id: number) =>
  useAction(
    (body: { source: SourceSpec; stream_mode?: "encode" | "passthrough" }) =>
      unwrap(api.PUT("/api/v1/cameras/{camera_id}/source", { params: { path: { camera_id: id } }, body })),
    { success: "Source changed (clients reconnect)", invalidate: () => camKeys(id) },
  )

/** PUT /cameras/{id}/state/{section}: the same document ONVIF reads and writes. */
export const usePutSection = <K extends keyof CameraState>(id: number, section: K, success: string | null = "Saved") =>
  useAction((value: CameraState[K]) => requestJson<CameraState[K]>("PUT", `/api/v1/cameras/${id}/state/${String(section)}`, value), {
    success: success ?? undefined,
    invalidate: () => camKeys(id),
  })

export const useAddCameraUser = (id: number) =>
  useAction(
    (body: { username: string; password: string; level: "Administrator" | "Operator" | "User" }) =>
      unwrap(api.POST("/api/v1/cameras/{camera_id}/users", { params: { path: { camera_id: id } }, body })),
    { success: (_, a) => `User ${a.username} added`, invalidate: () => [qk.camUsers(id)] },
  )

export const useUpdateCameraUser = (id: number) =>
  useAction(
    ({ username, ...body }: { username: string; password?: string | null; level?: "Administrator" | "Operator" | "User" | null }) =>
      unwrap(api.PATCH("/api/v1/cameras/{camera_id}/users/{username}", { params: { path: { camera_id: id, username } }, body })),
    { success: (_, a) => `User ${a.username} updated`, invalidate: () => [qk.camUsers(id)] },
  )

export const useDeleteCameraUser = (id: number) =>
  useAction(
    (username: string) => unwrap(api.DELETE("/api/v1/cameras/{camera_id}/users/{username}", { params: { path: { camera_id: id, username } } })),
    { success: (_, u) => `User ${u} deleted`, invalidate: () => [qk.camUsers(id)] },
  )

// ============================================================ events

export const useCameraEvents = (id: number) =>
  useQuery({
    queryKey: qk.events(id),
    queryFn: () => unwrap(api.GET("/api/v1/cameras/{camera_id}/events", { params: { path: { camera_id: id }, query: { limit: 200 } } })),
  })

export const useEventState = (id: number) =>
  useQuery({
    queryKey: qk.eventState(id),
    queryFn: () => unwrap(api.GET("/api/v1/cameras/{camera_id}/events/state", { params: { path: { camera_id: id } } })),
  })

export const useTriggerEvent = () =>
  useAction(
    ({ id, ...body }: TriggerIn & { id: number }) =>
      unwrap(api.POST("/api/v1/cameras/{camera_id}/events/trigger", { params: { path: { camera_id: id } }, body })),
    { success: (_, a) => `${a.kind.replace("_", " ")} ${a.state === false ? "off" : "on"}`, invalidate: (a) => [qk.eventState(a.id), qk.events(a.id)] },
  )

export const useBulkTrigger = () =>
  useAction((body: TriggerIn & { ids?: number[] | null }) => unwrap(api.POST("/api/v1/events/bulk-trigger", { body })), {
    success: (r) => `Event fired on ${r.triggered ?? 0} camera(s)`,
  })

export const useSchedules = (cameraId?: number) =>
  useQuery({
    queryKey: [...qk.schedules, cameraId ?? "all"],
    queryFn: () => unwrap(api.GET("/api/v1/event-schedules", { params: { query: cameraId ? { camera_id: cameraId } : {} } })),
  })

export const useCreateSchedule = () =>
  useAction((body: ScheduleIn) => unwrap(api.POST("/api/v1/event-schedules", { body })), {
    success: "Schedule created",
    invalidate: () => [qk.schedules],
  })

export const useUpdateSchedule = () =>
  useAction(
    ({ id, ...body }: ScheduleIn & { id: number }) =>
      unwrap(api.PATCH("/api/v1/event-schedules/{schedule_id}", { params: { path: { schedule_id: id } }, body })),
    { success: "Schedule updated", invalidate: () => [qk.schedules] },
  )

export const useDeleteSchedule = () =>
  useAction((id: number) => unwrap(api.DELETE("/api/v1/event-schedules/{schedule_id}", { params: { path: { schedule_id: id } } })), {
    success: "Schedule deleted",
    invalidate: () => [qk.schedules],
  })

// ============================================================ faults

export const useFaultTypes = () =>
  useQuery({ queryKey: qk.faultTypes, queryFn: () => unwrap(api.GET("/api/v1/faults/types")), staleTime: Infinity })

export const useApplyFault = () =>
  useAction(
    ({ id, ...body }: FaultIn & { id: number }) =>
      unwrap(api.POST("/api/v1/cameras/{camera_id}/faults", { params: { path: { camera_id: id } }, body })),
    { success: (_, a) => `Fault applied: ${a.type}`, invalidate: (a) => camKeys(a.id) },
  )

export const useClearFault = () =>
  useAction(
    ({ id, type }: { id: number; type: string }) =>
      unwrap(api.DELETE("/api/v1/cameras/{camera_id}/faults/{fault_type}", { params: { path: { camera_id: id, fault_type: type } } })),
    { success: (_, a) => (a.type === "all" ? "All faults cleared" : `Fault cleared: ${a.type}`), invalidate: (a) => camKeys(a.id) },
  )

export const useBulkFault = () =>
  useAction((body: FaultIn & { ids: number[] }) => unwrap(api.POST("/api/v1/faults/bulk", { body })), {
    success: (r, a) => `${a.type} applied to ${Object.values(r.results).filter((x) => x === "ok").length} camera(s)`,
    invalidate: () => [qk.cameras],
  })

export const useBulkClearFaults = () =>
  useAction((ids: number[]) => unwrap(api.POST("/api/v1/faults/bulk-clear", { body: ids })), {
    success: (r) => `${r.cleared ?? 0} fault(s) cleared`,
    invalidate: () => [qk.cameras],
  })

// ============================================================ inspector

export interface InspectorFilter {
  camera_id?: number
  op?: string
  client_ip?: string
  limit?: number
}

export const useInspector = (f: InspectorFilter, follow: boolean) =>
  useQuery({
    queryKey: [...qk.inspector, f],
    queryFn: () => unwrap(api.GET("/api/v1/inspector", { params: { query: { limit: 500, ...f } } })),
    select: (d) => d.items,
    refetchInterval: follow ? 3_000 : false,
    placeholderData: keepPreviousData,
  })

export const useInspectorEntry = (id: number | null) =>
  useQuery({
    queryKey: qk.inspectorEntry(id ?? 0),
    queryFn: () => unwrap(api.GET("/api/v1/inspector/{entry_id}", { params: { path: { entry_id: id! } } })),
    enabled: id != null,
    staleTime: Infinity,
  })

export const useClearInspector = () =>
  useAction((cameraId?: number) => unwrap(api.DELETE("/api/v1/inspector", { params: { query: cameraId ? { camera_id: cameraId } : {} } })), {
    success: "Inspector cleared",
    invalidate: () => [qk.inspector],
  })

// ============================================================ media library

export const useFsRoots = () => useQuery({ queryKey: qk.fsRoots, queryFn: () => unwrap(api.GET("/api/v1/fs/roots")), staleTime: 60_000 })

export const useBrowse = (path: string | null, showAll = false) =>
  useQuery({
    queryKey: [...qk.browse(path ?? ""), showAll],
    queryFn: () => unwrap(api.GET("/api/v1/fs/browse", { params: { query: { path: path!, show_all: showAll } } })),
    enabled: !!path,
    retry: false,
  })

/** ffprobe a path. A mutation (not a query) because it runs on demand and its errors are shown inline. */
export const useProbe = () => useMutation({ mutationFn: (path: string) => unwrap(api.POST("/api/v1/media/probe", { body: { path, label: "" } })) })

export const useMedia = () => useQuery({ queryKey: qk.media, queryFn: () => unwrap(api.GET("/api/v1/media")) })

export const useRegisterMedia = () =>
  useAction((body: { path: string; label: string }) => unwrap(api.POST("/api/v1/media", { body })), {
    success: "Footage registered",
    invalidate: () => [qk.media],
  })

export const useDeleteMedia = () =>
  useAction((id: number) => unwrap(api.DELETE("/api/v1/media/{media_id}", { params: { path: { media_id: id } } })), {
    success: "Removed from library (file not touched)",
    invalidate: () => [qk.media],
  })

export const useJobs = () => useQuery({ queryKey: qk.jobs, queryFn: () => unwrap(api.GET("/api/v1/media/jobs")), refetchInterval: 10_000 })

export const useRetryJobs = () =>
  useAction((path?: string) => unwrap(api.POST("/api/v1/media/jobs/retry", { params: { query: path ? { path } : {} } })), {
    success: (r) => `${r.retried ?? 0} job(s) retried`,
    invalidate: () => [qk.jobs],
  })

// ============================================================ templates

export const useTemplates = () => useQuery({ queryKey: qk.templates, queryFn: () => unwrap(api.GET("/api/v1/templates")), staleTime: 60_000 })

export const useCreateTemplate = () =>
  useAction((body: { key: string; definition: Record<string, unknown> }) => unwrap(api.POST("/api/v1/templates", { body })), {
    success: "Template saved",
    invalidate: () => [qk.templates],
  })

export const useCloneTemplate = () =>
  useAction(
    ({ key, newKey }: { key: string; newKey: string }) =>
      unwrap(api.POST("/api/v1/templates/{key}/clone", { params: { path: { key }, query: { new_key: newKey } } })),
    { success: "Template cloned", invalidate: () => [qk.templates] },
  )

export const useDeleteTemplate = () =>
  useAction((key: string) => unwrap(api.DELETE("/api/v1/templates/{key}", { params: { path: { key } } })), {
    success: "Template deleted",
    invalidate: () => [qk.templates],
  })

// ============================================================ PTZ (manager side)

export const usePtzStatus = (id: number, enabled: boolean) =>
  useQuery({
    queryKey: ["cameras", id, "ptz"],
    queryFn: () => unwrap(api.GET("/api/v1/cameras/{camera_id}/ptz/status", { params: { path: { camera_id: id } } })),
    enabled,
    refetchInterval: enabled ? 1_000 : false,
  })

export const ptzApi = {
  move: (id: number, pan: number, tilt: number, zoom: number) =>
    unwrap(api.POST("/api/v1/cameras/{camera_id}/ptz/move", { params: { path: { camera_id: id } }, body: { pan, tilt, zoom, timeout_s: 2 } })),
  stop: (id: number) => unwrap(api.POST("/api/v1/cameras/{camera_id}/ptz/stop", { params: { path: { camera_id: id } } })),
  goto: (id: number, token: string) =>
    unwrap(api.POST("/api/v1/cameras/{camera_id}/ptz/presets/{preset_token}/goto", { params: { path: { camera_id: id, preset_token: token } } })),
  home: (id: number) => unwrap(api.POST("/api/v1/cameras/{camera_id}/ptz/home", { params: { path: { camera_id: id } } })),
}

export const useMe = () => useQuery({ queryKey: qk.me, queryFn: () => unwrap(api.GET("/api/v1/auth/me")) as Promise<{ username: string }>, staleTime: Infinity })
