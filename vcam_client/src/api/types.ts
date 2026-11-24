/** Short names for the generated API types (src/api/manager.d.ts, src/api/camera.d.ts). */
import type { components as Cam } from "./camera"
import type { components as M } from "./manager"

type S = M["schemas"]
type C = Cam["schemas"]

// ---- Manager API ----
export type Camera = S["CameraOut"]
export type CameraCreate = S["CameraCreate"]
export type CameraPatch = S["CameraPatch"]
export type BulkCreate = S["BulkCreate"]
export type BulkAction = S["BulkAction"]["action"]
export type BulkSourceIn = S["BulkSourceIn"]
export type SourceSpec = S["SourceSpec-Output"]
export type SourceSpecIn = S["SourceSpec-Input"]
export type CameraUrls = S["CameraUrls"]
export type Clients = S["ClientsOut"]
export type CameraUser = S["CameraUserOut"]
export type Stats = S["StatsOut"]
export type FarmStats = S["FarmStats"]
export type CameraStats = S["CameraStats"]
export type Health = S["HealthOut"]
export type Nic = S["NicOut"]
export type EventItem = S["EventOut"]
export type EventState = S["EventStateOut"]
export type Schedule = S["ScheduleOut"]
export type ScheduleIn = S["ScheduleIn"]
export type TriggerIn = S["TriggerIn"]
export type Fault = S["FaultOut"]
export type FaultType = S["FaultTypeOut"]
export type FaultIn = S["FaultIn"]
export type InspectorSummary = S["InspectorSummary"]
export type InspectorEntry = S["InspectorEntryOut"]
export type Probe = S["ProbeOut"]
export type FsEntry = S["FsEntry"]
export type Browse = S["BrowseOut"]
export type MediaItem = S["MediaItemOut"]
export type Job = S["JobOut"]
export type Template = S["TemplateOut"]
export type AdminUser = S["AdminUserOut"]

// ---- CameraState (same document on both APIs) ----
export type CameraState = C["CameraState"]
export type VideoEncoder = C["VideoEncoderConfig"]
export type StreamOptions = C["StreamOptions"]
export type Imaging = C["ImagingSettings"]
export type OsdItem = C["OsdItem"]
export type NetworkState = C["NetworkState"]
export type TimeState = C["TimeState"]
export type Identity = C["Identity"]
export type IoState = C["IoState"]
export type PtzPreset = C["PtzPreset"]

// ---- Camera web API ----
export type CamSession = C["SessionOut"]
export type CamDevice = C["DeviceOut"]
export type CamStreams = C["StreamsOut"]
export type CamPtzStatus = C["PtzStatusOut"]
export type CamUser = C["CamUser"]

export type CameraStatus = "running" | "starting" | "rebooting" | "offline" | "stopping" | "stopped" | "error"

