# VirtualCamX – Feature Specification

**Version:** 0.1 (Draft, for feature lock)
**Date:** 2026-11-23
**Status:** Waiting for feature lock. The implementation plan comes after this.

**What this is:** a software-only **virtual IP camera farm**. One VirtualCamX install creates
**many virtual cameras**. On the network, each one looks and behaves like a real ONVIF IP camera.
Its only purpose is to **test NVRs/VMSs** (Shah-NVR, Hikvision/Dahua NVRs, Milestone, Nx Witness, Frigate, and others)
without buying or wiring real cameras.

**What this is not:** it is not a real camera firmware, not an AI analytics product, and not an NVR.
It does not need real sensors, real AI, or real cloud features. It only needs to be **believable to an NVR**.

**Priority key** (same as `virtual_camera.md`):
- **P0**: must have for v1.0 (MVP). Without it, an NVR cannot use the camera properly.
- **P1**: expected soon after (v1.1). Makes it a strong test tool.
- **P2**: later / nice to have.

---

## 1. Goals

1. **"An NVR cannot tell the difference."** An NVR discovers, adds, streams, configures, and gets events from a
   virtual camera exactly as it does from a real ONVIF camera.
2. **Many cameras from one machine.** Create 1 to 200+ cameras in one click (bulk create), each with its own identity.
3. **Full ONVIF Profile S + T** in v1, plus Profile G and M later.
4. **Two web UIs:**
   - a **Manager UI** to create and control the whole camera farm, and
   - a **per-camera web page** that looks and works like a real IP camera's web interface.
5. **Built for testing.** Simulate events, inject faults (stream drop, reboot, wrong time, and so on), and inspect
   every ONVIF request the NVR sends.
6. **Keep it simple.** One server process, one media server, one database, one web client.

---

## 2. How It Works (Big Picture)

```
                        ┌───────────────────────── VirtualCamX host ─────────────────────────┐
                        │                                                                     │
  NVR / VMS             │   vcam_server (FastAPI, Python)                                     │
  ─────────             │   ├─ WS-Discovery responder (UDP 3702, multicast)                   │
  1. Discover  ───────────►├─ ONVIF SOAP services (Device, Media, Media2, Events, PTZ, ...)   │
  2. Add camera ───────────►├─ Per-camera web page + REST API                                 │
  3. GetStreamUri ─────────►├─ Manager REST API + Manager UI                                  │
                        │   ├─ Event simulator + Fault injector                               │
                        │   └─ Stream supervisor (starts/stops FFmpeg per stream)             │
                        │              │                                                      │
                        │              ▼                                                      │
                        │   FFmpeg workers ──publish──► MediaMTX (RTSP 554/8554, WebRTC, HLS) │
  4. RTSP pull  ◄──────────────────────────────────────── rtsp://<cam-ip>:<port>/cam001/main  │
                        │                                                                     │
                        │   SQLite (cameras, profiles, users, events, logs)                   │
                        └─────────────────────────────────────────────────────────────────────┘
```

- **One source of truth:** each camera's config lives in the database. A change made through ONVIF shows up in the web
  UI, and a change made in the web UI is returned by ONVIF. This is how a real camera behaves.
- **One process for all cameras.** A request is routed to the right camera by **port** (Port Mode) or by the
  **destination IP** (IP Mode). See section 3.

---

## 3. Camera Identity & Networking

A real NVR identifies a camera by **IP + port**. So each virtual camera must have its own address.

### 3.1 Addressing Modes

| Mode | How a camera is addressed | Setup | Realism | Priority |
|---|---|---|---|---|
| **Port Mode** (default) | Same host IP, a different port per camera. Camera 1 = HTTP 8001, Camera 2 = 8002, and so on. RTSP is shared on 8554 with a unique path. | Zero setup | Good. Works with any NVR that allows a custom ONVIF port. | **P0** |
| **IP Mode** | Each camera gets its **own IP** (an IP alias on the host NIC), with standard ports 80 / 554. | VirtualCamX adds or removes IP aliases (needs admin rights). | Excellent. Same as real cameras, and works with NVRs that only use port 80. | **P1** |

- An auto allocator assigns the next free port or IP from a configured range (for example `8001–8999` or `192.168.1.201–250`).
- Camera ports and IPs can also be edited by hand.
- In IP Mode, one listener on `0.0.0.0:80` serves all cameras, and the camera is chosen by the local destination IP.
  MediaMTX serves RTSP the same way.
- Windows (`netsh`) and Linux (`ip addr`) are supported. Docker with macvlan is P2.

### 3.2 Per-Camera Identity (Fully Editable)

| Field | Example | Notes |
|---|---|---|
| Name | `VCam-Gate-01` | Shown in the OSD and in the web UI |
| Manufacturer | `VirtualCamX` | Editable, so you can test how an NVR handles different vendors |
| Model | `VCX-IPC-4MP` | |
| Firmware version | `V1.0.0 build 261123` | |
| Serial number | auto-generated, unique | |
| Hardware ID | | |
| MAC address | auto-generated (locally administered range), unique | |
| ONVIF scopes | `onvif://www.onvif.org/name/...`, `/location/...`, `/hardware/...`, `/Profile/Streaming`, `/Profile/T` | |
| Endpoint UUID | `urn:uuid:...`, unique and stable | Used by WS-Discovery |

### 3.3 Camera Templates ("Models")

- A **template** = identity defaults + stream profiles + capabilities (PTZ yes/no, audio yes/no, number of I/O, and so on).
- Built-in templates: **Bullet 2MP**, **Bullet 4MP**, **Dome 5MP**, **PTZ 2MP**, **Fisheye 12MP** (P2), **Low-end 720p**.
- Users can create, clone, and edit their own templates. Bulk create always uses a template.

---

## 4. ONVIF Compatibility (Core of the Product)

**Target:** pass the **ONVIF Device Test Tool** core tests for Profile S and Profile T, and work with **ONVIF Device
Manager**. Official ONVIF certification is out of scope, because it needs membership and is not needed for a test tool.

### 4.1 Profiles

| Profile | Purpose | Priority |
|---|---|---|
| **S** | Streaming, Media1, PTZ, relay output | **P0** |
| **T** | Media2, H.265, OSD, imaging, motion/tamper events, HTTPS | **P0** |
| **G** | Edge recording: recordings, search, replay | P2 |
| **M** | Analytics metadata stream and analytics rules | P2 |
| A / C / D (access control) | Not relevant for cameras | Out of scope |

### 4.2 Transport & Security

| # | Feature | Priority |
|---|---|---|
| 4.2.1 | SOAP 1.2 over HTTP, `/onvif/device_service` and one endpoint per service | P0 |
| 4.2.2 | **WS-Security UsernameToken** (PasswordDigest + PasswordText) | P0 |
| 4.2.3 | **HTTP Digest** authentication (some NVRs use this instead of WS-Security) | P0 |
| 4.2.4 | Correct handling of the time offset between NVR and camera for the WS-Security `Created` field, plus replay checks on nonce | P0 |
| 4.2.5 | Unauthenticated calls allowed per the ONVIF spec (`GetSystemDateAndTime`, `GetServices`, `GetCapabilities`, `GetDeviceInformation` optional) | P0 |
| 4.2.6 | Correct SOAP faults (`ter:NotAuthorized`, `ter:InvalidArgVal`, `ter:ActionNotSupported`, and so on) | P0 |
| 4.2.7 | ONVIF user levels: Administrator / Operator / User / Anonymous, enforced per operation | P0 |
| 4.2.8 | HTTPS for ONVIF and the web page (self-signed cert per install) | P1 |
| 4.2.9 | WS-Discovery: respond to `Probe` (any type, `NetworkVideoTransmitter`, `Device`, scopes), send `Hello` on start and `Bye` on stop, with discoverable / non-discoverable mode per camera | P0 |

### 4.3 Device Service (P0)

`GetServices`, `GetServiceCapabilities`, `GetCapabilities`, `GetDeviceInformation`, `GetSystemDateAndTime`,
`SetSystemDateAndTime`, `GetHostname`, `SetHostname`, `GetNetworkInterfaces`, `SetNetworkInterfaces`*,
`GetNetworkProtocols`, `SetNetworkProtocols`*, `GetNetworkDefaultGateway`, `GetDNS`, `SetDNS`, `GetNTP`, `SetNTP`,
`GetScopes`, `SetScopes`, `AddScopes`, `RemoveScopes`, `GetDiscoveryMode`, `SetDiscoveryMode`, `GetUsers`,
`CreateUsers`, `DeleteUsers`, `SetUser`, `SystemReboot`, `SetSystemFactoryDefault`, `GetSystemLog`,
`GetRelayOutputs`, `SetRelayOutputSettings`, `SetRelayOutputState`, `GetWsdlUrl`, `GetZeroConfiguration`,
`GetEndpointReference`.

\* Network "Set" calls are **stored and reported back** but not applied to the host network.
In IP Mode, a changed IP can optionally move the camera to the new IP alias (P2).

### 4.4 Media Service – Profile S (Media1, P0)

`GetProfiles`, `GetProfile`, `CreateProfile`, `DeleteProfile`, `GetVideoSources`,
`GetVideoSourceConfigurations`, `GetVideoSourceConfiguration`, `GetCompatibleVideoSourceConfigurations`,
`AddVideoSourceConfiguration`, `GetVideoEncoderConfigurations`, `GetVideoEncoderConfiguration`,
`SetVideoEncoderConfiguration`, `GetVideoEncoderConfigurationOptions`, `GetCompatibleVideoEncoderConfigurations`,
`AddVideoEncoderConfiguration`, `RemoveVideoEncoderConfiguration`, `GetAudioSources`,
`GetAudioSourceConfigurations`, `GetAudioEncoderConfigurations`, `SetAudioEncoderConfiguration`,
`GetAudioEncoderConfigurationOptions`, `GetMetadataConfigurations`, `GetStreamUri` (RTP-Unicast, RTSP / RTP over RTSP /
HTTP tunnel), `GetSnapshotUri`, `SetSynchronizationPoint`, `StartMulticastStreaming` / `StopMulticastStreaming` (P1).

### 4.5 Media2 Service – Profile T (P0)

`GetProfiles`, `CreateProfile`, `DeleteProfile`, `AddConfiguration`, `RemoveConfiguration`,
`GetVideoSourceConfigurations`, `GetVideoEncoderConfigurations`, `SetVideoEncoderConfiguration`,
`GetVideoEncoderConfigurationOptions`, `GetAudioEncoderConfigurations`, `GetMetadataConfigurations`,
`GetStreamUri`, `GetSnapshotUri`, `SetSynchronizationPoint`, `GetOSDs`, `GetOSDOptions`, `CreateOSD`, `SetOSD`,
`DeleteOSD`, `GetMasks`, `CreateMask`, `SetMask`, `DeleteMask` (privacy masks, P1).

### 4.6 Events Service (P0)

- **PullPoint:** `CreatePullPointSubscription`, `PullMessages`, `Renew`, `Unsubscribe`, `SetSynchronizationPoint`
  (re-sends the current state of all property events).
- **Base notification (push):** `Subscribe` to the NVR's consumer URL, `Renew`, `Unsubscribe` (P0, because some NVRs use only push).
- `GetEventProperties` (topic set), `GetServiceCapabilities`.
- Topic filters (`TopicExpression`) supported in subscriptions.
- Supported topics:

| Topic | Data | Priority |
|---|---|---|
| `tns1:VideoSource/MotionAlarm` | `State` | P0 |
| `tns1:RuleEngine/CellMotionDetector/Motion` | `IsMotion` | P0 |
| `tns1:VideoSource/GlobalSceneChange/ImagingService` (tamper) | `State` | P0 |
| `tns1:Device/Trigger/DigitalInput` | `LogicalState` | P0 |
| `tns1:Device/Trigger/Relay` | `LogicalState` | P0 |
| `tns1:VideoSource/SignalLoss` (video loss) | `State` | P1 |
| `tns1:RuleEngine/LineDetector/Crossed` | `ObjectId` | P1 |
| `tns1:RuleEngine/FieldDetector/ObjectsInside` (intrusion) | `IsInside` | P1 |
| `tns1:RuleEngine/MyRuleDetector/PeopleDetect` / VehicleDetect | `State` | P2 |
| `tns1:Device/HardwareFailure/StorageFailure` | `Failed` | P2 |

### 4.7 Imaging Service (P0)

`GetImagingSettings`, `SetImagingSettings`, `GetOptions`, `GetMoveOptions`, `Move`, `Stop`, `GetStatus`.
Settings: brightness, contrast, saturation, sharpness, IR cut filter (ON/OFF/AUTO), backlight, WDR, exposure,
white balance, focus.
In **Encode Mode** (section 5.2), brightness, contrast, saturation, and IR-cut "night mode" (grayscale) are **really
applied** to the video with FFmpeg filters, so a tester can see the change. In Passthrough Mode they are only stored.

### 4.8 PTZ Service (P0 for PTZ templates)

`GetNodes`, `GetNode`, `GetConfigurations`, `GetConfiguration`, `GetConfigurationOptions`, `SetConfiguration`,
`ContinuousMove`, `RelativeMove`, `AbsoluteMove`, `Stop`, `GetStatus`, `GetPresets`, `SetPreset`, `GotoPreset`,
`RemovePreset`, `GotoHomePosition`, `SetHomePosition`.
- **Virtual PTZ:** the camera keeps a real position (pan, tilt, zoom) that moves over time at the requested speed.
- In Encode Mode, the view **really pans and zooms** (a digital crop over a larger source image), so the NVR's PTZ
  controls give visible feedback.
- Up to 256 presets, plus home position.

### 4.9 DeviceIO Service (P0)

`GetVideoSources`, `GetVideoOutputs`, `GetRelayOutputs`, `SetRelayOutputSettings`, `SetRelayOutputState`,
`GetDigitalInputs`, `GetAudioOutputs`, `GetAudioSources`.
Virtual I/O: inputs are toggled from the UI or API and raise events. Relay state is set by the NVR and shown in the UI.

### 4.10 Later Services

| Service | Operations | Priority |
|---|---|---|
| Recording / Search / Replay (Profile G) | `GetRecordings`, `GetRecordingSummary`, `FindRecordings`, `FindEvents`, `GetRecordingSearchResults`, `GetReplayUri`. Backed by a looped "fake" SD card made of real recorded chunks | P2 |
| Analytics (Profile M) | `GetSupportedAnalyticsModules`, `GetAnalyticsModules`, `GetSupportedRules`, `GetRules`, plus an RTSP metadata track with simulated bounding boxes | P2 |
| Audio backchannel | Two-way audio: the NVR sends audio to the camera (`www.onvif.org/ver20/backchannel`) | P2 |

---

## 5. Video & Audio Streams

### 5.1 Video Sources (What the Camera "Sees")

| Source | Description | Priority |
|---|---|---|
| **Test pattern** | Generated (color bars / moving pattern) with a burned-in camera name, live clock, and frame counter. No files needed. | P0 |
| **Video file loop (by path)** | The user gives the **path of a video file** (for example `D:\Footage\gate_day.mp4`). The camera streams that file directly, looped endlessly. **No upload or copy.** See 5.1.1. | **P0** |
| **Folder playlist (by path)** | The user gives a **folder path**. The camera plays all videos in it one after another, then loops. | P1 |
| **Video file loop (uploaded)** | A video uploaded into the Media Library from a browser on another PC | P1 |
| **Image** | Still JPEG/PNG turned into a stream (with a moving clock overlay) | P1 |
| **RTSP relay** | Re-publish a real camera's stream as this virtual camera | P1 |
| **Webcam / screen capture** | Local device as the source | P2 |

Several cameras can **share one source file**, so 100 cameras do not need 100 files.

#### 5.1.1 Use Your Own Footage by File Path (P0)

The user picks real footage (gate, parking, road, office, night/IR clips, and so on) and the camera streams it.
The file is **used in place**. It is never uploaded, copied, or moved.

| # | Behavior | Priority |
|---|---|---|
| 5.1.1.1 | In the Manager UI (camera create/edit → **Source**), choose "Video file" and enter or paste the path | P0 |
| 5.1.1.2 | **Server file browser:** a "Browse…" dialog lists the folders and files on the VirtualCamX machine, so the user does not have to type paths | P0 |
| 5.1.1.3 | The path is checked right away with `ffprobe`: the file exists, it is readable, and it has a video track. The UI shows codec, resolution, FPS, duration, and audio. A bad path or file shows a clear error. | P0 |
| 5.1.1.4 | **Change footage live:** a running camera switches to the new file without being deleted or re-added. The NVR sees only a short stream reconnect, the same as a real camera after a settings change. | P0 |
| 5.1.1.5 | Supported formats: anything FFmpeg can read (MP4, MKV, AVI, MOV, TS, and others) | P0 |
| 5.1.1.6 | **Bulk assign:** set one file or folder for many cameras at once. Optional "spread" option: give each selected camera a different file from a folder, so the NVR wall does not show 50 identical views. | P1 |
| 5.1.1.7 | **Start offset per camera:** cameras sharing one file start at different points, so they do not look identical | P1 |
| 5.1.1.8 | **Missing file at runtime** (for example a USB drive is removed): the camera shows a "NO SOURCE" test pattern, logs a warning, and recovers when the file returns. The camera stays online for the NVR. | P1 |
| 5.1.1.9 | **Recent paths / favorites** list for quick reuse | P2 |

**How the file is streamed (links to 5.2):**
- **Encode Mode:** the file is decoded and re-encoded live into each stream profile. Any input file works with any
  profile settings.
- **Passthrough Mode:** if the file already matches a profile (for example H.264 1080p), it is streamed as-is with no
  re-encoding, so the cost is near zero. If it does not match, VirtualCamX encodes it **once** into a cache folder
  (`cache/<file-hash>/<profile>.mp4`) and streams from the cache after that. The original file is never changed.
  The cache is rebuilt automatically if the original file changes.

**Note:** a path always means a path **on the machine running VirtualCamX**. If the browser runs on the same PC
(the usual case), this is just your local disk. Network shares (for example `\\NAS\footage\cam1.mp4`) also work if
the server can read them.

### 5.2 Stream Modes (Important for Scale)

| Mode | How it works | CPU cost | Honors encoder changes? | Priority |
|---|---|---|---|---|
| **Passthrough** | Media Library files are pre-encoded once into each profile (for example 1080p H.265 4 Mbps and D1 H.264 512 kbps). Streams are copied without re-encoding. | Very low, so **hundreds** of cameras on one PC | Picks the closest pre-encoded variant | **P0** |
| **Encode** | FFmpeg encodes live for each stream | ~0.5–1 CPU core per 1080p stream | **Yes.** Resolution, FPS, bitrate, GOP, codec, OSD, image settings, and PTZ are all live. | **P0** |
| **GPU Encode** | Same as Encode, using NVENC / QSV / AMF | Low CPU | Yes | P2 |

Mode is chosen per camera. A typical test lab uses **a few Encode cameras** (to test configuration) and **many
Passthrough cameras** (to test load and scale).

### 5.3 Stream Profiles

| # | Feature | Priority |
|---|---|---|
| 5.3.1 | Up to **3 streams** per camera: Main, Sub, Third | P0 |
| 5.3.2 | Codecs: **H.264, H.265, MJPEG** | P0 |
| 5.3.3 | Resolution: from 352×288 up to 3840×2160 (the list depends on the template) | P0 |
| 5.3.4 | Frame rate 1–30 fps, GOP / I-frame interval, H.264 profile (Baseline/Main/High) | P0 |
| 5.3.5 | Bitrate control: CBR / VBR, bitrate limit, quality | P0 |
| 5.3.6 | RTSP over UDP, TCP (interleaved), and HTTP tunnel | P0 |
| 5.3.7 | RTSP authentication (Digest) using the camera's own user list | P0 |
| 5.3.8 | RTSP multicast | P1 |
| 5.3.9 | RTSPS (TLS) | P2 |
| 5.3.10 | **Snapshot** JPEG over HTTP (`GetSnapshotUri`), with Digest auth | P0 |
| 5.3.11 | MJPEG over HTTP (old NVRs) | P2 |
| 5.3.12 | Stream URL format editable per camera (to mimic vendor URL styles, for example `/Streaming/Channels/101`) | P1 |

### 5.4 OSD (On-Screen Display)

- Camera name and date/time (format and position editable), plus custom text lines (P0 in Encode Mode).
- Optional "test overlay": frame counter + millisecond clock, to **measure NVR latency and dropped frames** (P1).
- OSD is editable through ONVIF Media2 OSD calls and the web UI.

### 5.5 Audio

| # | Feature | Priority |
|---|---|---|
| 5.5.1 | Audio track on the stream: **G.711 µ-law/A-law, AAC** | P1 |
| 5.5.2 | Audio sources: from the video file, a test tone, or silence | P1 |
| 5.5.3 | Enable/disable audio per profile (ONVIF audio encoder config) | P1 |
| 5.5.4 | Two-way audio backchannel | P2 |

---

## 6. Testing Features (What Makes It a Test Tool)

### 6.1 Event Simulator

| # | Feature | Priority |
|---|---|---|
| 6.1.1 | **Manual trigger** buttons per camera: Motion start/stop, Tamper, Digital Input ON/OFF | P0 |
| 6.1.2 | **Scheduled / periodic** events: for example "motion for 10 s every 60 s" | P0 |
| 6.1.3 | **Random** events (random interval within min/max) for soak tests | P1 |
| 6.1.4 | Bulk trigger: fire an event on selected cameras or all cameras at once (NVR event-load test) | P1 |
| 6.1.5 | Events also burned into the video OSD (for example "MOTION") so the tester can match events to video | P1 |
| 6.1.6 | REST API to trigger any event (for automated NVR test scripts) | P0 |
| 6.1.7 | Real motion detection on the source video (frame diff) | P2 |

### 6.2 Fault Injection (Simulate Real-World Camera Problems)

| # | Fault | What the NVR sees | Priority |
|---|---|---|---|
| 6.2.1 | **Camera offline** | ONVIF and RTSP stop responding (port closed) | P0 |
| 6.2.2 | **Stream drop** | RTSP session is cut; ONVIF still works | P0 |
| 6.2.3 | **Reboot** | Offline for N seconds, then back up with a new boot time (also triggered by ONVIF `SystemReboot`) | P0 |
| 6.2.4 | **Video freeze** | Stream continues but the frame does not change | P1 |
| 6.2.5 | **Video loss / black screen** | Black frames plus a `SignalLoss` event | P1 |
| 6.2.6 | **Clock drift** | Camera time is off by N minutes (tests NVR time sync and WS-Security) | P1 |
| 6.2.7 | **Password changed** | Credentials change, and the NVR gets `NotAuthorized` | P1 |
| 6.2.8 | **Slow ONVIF** | Adds a delay (for example 3 s) to every SOAP response | P1 |
| 6.2.9 | **Resolution/codec change mid-stream** | Tests the NVR's decoder recovery | P1 |
| 6.2.10 | **Flapping** | Goes offline/online on a schedule | P1 |
| 6.2.11 | **ONVIF fault** on selected operations | Returns a SOAP fault for, say, `GetStreamUri` | P2 |
| 6.2.12 | Network impairment: packet loss, jitter, bandwidth cap | | P2 |

### 6.3 ONVIF Traffic Inspector (Debug)

- Logs every ONVIF request and response per camera: time, client IP, operation, auth result, duration,
  and full SOAP XML (P0).
- Filter by camera, operation, or client. Export to file (P1).
- Shows **which NVR** is connected and which operations it uses, so you can quickly see why an NVR is failing.

### 6.4 Stream Monitor

- Per camera: connected RTSP clients (IP, transport, since), current bitrate, FPS, and FFmpeg worker status (P0).
- Farm totals: total outgoing bandwidth and CPU/RAM of the host (P0).

---

## 7. Web UI

The client is React 19 + TypeScript. Live view uses WebRTC from MediaMTX (no plugins).

### 7.1 Manager UI (Camera Farm Console)

Opened at `http://<host>:9000/`. This is the admin console for the whole farm.

```
VirtualCamX Manager
├─ Dashboard         Totals: cameras, running, offline, clients, bandwidth, CPU/RAM, recent events
├─ Cameras           Table + grid view of all cameras
│   ├─ Create camera (single)
│   ├─ Bulk create   "Create 50 cameras from template 'Bullet 4MP', names VCam-{001..050}, ports from 8001"
│   ├─ Bulk actions  Start / Stop / Restart / Delete / Change source / Trigger event / Inject fault
│   └─ Camera detail Overview, live view, URLs (ONVIF / RTSP / snapshot), clients, events, logs,
│                    "Open camera web page" button
├─ Live Wall         Grid of live views (4 / 9 / 16 tiles)
├─ Media Library     Footage registered by file/folder path (server file browser + ffprobe info),
│                    passthrough cache status; uploading from another PC is P1
├─ Templates         Camera models (identity + profiles + capabilities)
├─ Event Simulator   Manual / scheduled / random events, per camera or bulk
├─ Fault Injection   Apply/clear faults, per camera or bulk, with a timer
├─ ONVIF Inspector   Live request log with XML viewer
└─ Settings          Addressing mode (Port/IP), port and IP ranges, NIC selection,
                     discovery on/off, media server ports, admin users, backup/restore
```

Cameras table columns: status light, name, address (IP:port), template, source, mode (Passthrough/Encode),
streams, connected clients, bitrate, active faults, and actions.

Must-haves for the Manager UI (P0): dashboard, cameras list, single and bulk create, start/stop, live view,
copy URLs, Media Library, manual event triggers, basic faults, and ONVIF Inspector.

### 7.2 Per-Camera Web Page ("Real Camera" UI)

Each camera has its own web page, the same as a real IP camera:
- **IP Mode:** `http://<camera-ip>/`
- **Port Mode:** `http://<host>:<camera-port>/`

It has its own login (the camera's own users) and only shows that one camera. It looks like a typical camera web
interface:

```
[ VCam-Gate-01 ]                                Live View | Playback* | Configuration | Logout
──────────────────────────────────────────────────────────────────────────────────────────────
Live View        Live video (Main/Sub switch), snapshot, full screen, PTZ pad + presets (PTZ models),
                 relay output button
Configuration
├─ System        Device info (model, serial, firmware, MAC), Time (manual/NTP, timezone),
│                Maintenance (reboot, factory reset, "firmware upgrade"*, config export/import),
│                System log
├─ Network       TCP/IP (IP, mask, gateway, DNS), Ports (HTTP, HTTPS, RTSP), ONVIF (enable,
│                discovery mode, auth mode), Multicast
├─ Video/Audio   Main / Sub / Third stream: codec, resolution, FPS, bitrate type, bitrate, GOP,
│                profile; Audio: codec, enable
├─ Image         Brightness, contrast, saturation, sharpness, day/night (IR cut), WDR, mirror/flip
├─ OSD           Camera name, date/time format and position, custom text
├─ Privacy Mask  Draw up to 4 masks (P1)
├─ PTZ           Presets, home position, speed (PTZ models)
├─ Events        Motion detection (enable, sensitivity, area*), Tamper, Digital input, Relay output
├─ Users         Admin / Operator / Viewer users (the same list ONVIF GetUsers returns)
└─ Security      Authentication mode (digest / WS-Security / both), HTTPS certificate (P1)
```
\* "Firmware upgrade" accepts a file, simulates progress and reboot, and bumps the version string. Nothing is flashed.
\* Motion "area" is drawn and stored only. Real motion detection is P2.
\* Playback appears only when Profile G (P2) is on.

Priority: Live View, System, Network, Video, Image, OSD, Events, and Users are **P0**. Privacy Mask, PTZ page
polish, and Security page are **P1**.

### 7.3 REST API

- Versioned `/api/v1/...` with an OpenAPI spec (P0). Everything the Manager UI can do is available through the API,
  so NVR test suites can create cameras, trigger events, and inject faults from scripts.
- Token authentication for the Manager API (P0).
- WebSocket for live status, events, and the ONVIF log (P1).

---

## 8. Scale & Performance Targets

| Scenario | Target (mid-range PC: 8 cores, 16 GB RAM, 1 Gbps NIC) |
|---|---|
| Passthrough cameras (main 1080p 4 Mbps + sub 512 kbps) | **≥ 150 cameras** (about 680 Mbps, so the network is the limit, not the CPU) |
| Encode cameras (1080p H.264 main + D1 sub) | **8–12 cameras** (CPU limited) |
| ONVIF response time | < 100 ms per call when the farm is idle |
| WS-Discovery | Answers for all cameras in < 1 s |
| Camera start time | < 3 s from "Start" to RTSP ready |
| Bulk create 100 cameras | < 30 s |

Bitrate for each passthrough profile can be lowered to fit more cameras on one NIC.

---

## 9. Compatibility Test Matrix (Acceptance)

v1.0 is "done" when the virtual camera passes these tests:

| Client | Tests | Priority |
|---|---|---|
| **ONVIF Device Manager** (ODM) | Discover, log in, live view, change encoder settings, events, PTZ | P0 |
| **ONVIF Device Test Tool** | Profile S and T core test cases (diagnostic run) | P0 |
| **Shah-NVR** (own NVR, `media_node` ONVIF) | Add via discovery, record, events, PTZ | P0 |
| **VLC / FFplay** | RTSP UDP/TCP for every profile | P0 |
| Hikvision NVR and Dahua NVR (add as ONVIF camera) | Add, stream, motion events | P1 |
| Milestone XProtect, Nx Witness, Blue Iris, Frigate, Agent DVR | Add, stream, events | P1 |

---

## 10. Tech Stack (Matches `CODING_STYLE.md`)

| Part | Technology |
|---|---|
| Server | Python 3, **FastAPI** + Uvicorn, async, Pydantic v2, pydantic-settings |
| ONVIF SOAP | Own lightweight SOAP layer: **lxml** to parse requests, **Jinja2** XML templates for responses. Spyne/zeep are not used because they give less control over the exact XML NVRs expect. |
| WS-Discovery | Own asyncio UDP multicast responder |
| Media | **MediaMTX** (RTSP, WebRTC, HLS) + **FFmpeg** workers, with RTSP auth via MediaMTX's HTTP auth hook calling `vcam_server` |
| Database | **SQLite** + Tortoise ORM (`generate_schemas=True`, single node) |
| Web client | **React 19 + TypeScript** (Vite). One app with two shells: Manager UI and Camera Web Page. |
| Tests | pytest. ONVIF golden-XML tests plus an integration test with `onvif-zeep` acting as an "NVR". |
| Platforms | Windows 10/11 and Linux. Docker is P2. |

Planned folder layout (details in the implementation plan):
```
VirtualCamX/
├─ vcam_server/        # FastAPI service (main.py, settings/, app/cameras, app/onvif, app/discovery,
│                      #   app/streams, app/events, app/faults, app/media_library, app/inspector ...)
├─ vcam_client/        # React web client (manager + camera page)
├─ bin/                # mediamtx, ffmpeg binaries
├─ doc/
└─ plan/
```

---

## 11. Out of Scope (v1)

- Real AI analytics (person/vehicle detection). Analytics events are **simulated** only.
- Vendor-specific proprietary APIs (Hikvision ISAPI, Dahua CGI, private SDK protocols). P2 idea: "vendor emulation"
  for NVRs that refuse non-native cameras.
- Cloud / P2P, mobile app, SD card management, 802.1X, SNMP, MQTT, webhooks.
- Firmware security compliance (EU CRA and so on) from `virtual_camera.md`. Not needed for a test tool.
- Official ONVIF certification.

---

## 12. Release Phases (Suggested)

### v1.0 – MVP (all P0)
- Port Mode addressing, templates, single and bulk create.
- ONVIF Profile S + T: Device, Media, Media2, Events (pull + push), Imaging, PTZ, DeviceIO, WS-Discovery,
  WS-Security + Digest.
- Test pattern source + **your own footage by file path** (server file browser, ffprobe check, live switching);
  Passthrough and Encode modes; 3 streams; H.264/H.265/MJPEG; snapshot.
- Event simulator (manual + scheduled + API); faults: offline, stream drop, reboot.
- Manager UI (core pages) + per-camera web page (core pages) + REST API.
- ONVIF Traffic Inspector and stream monitor.

### v1.1 (P1)
- IP Mode (own IP per camera on ports 80/554), HTTPS.
- Audio, RTSP relay and image sources, folder playlists, bulk footage assign with spread and start offset,
  browser upload, multicast, custom stream URL formats.
- More events (line crossing, intrusion, video loss) and more faults (freeze, clock drift, slow ONVIF, flapping...).
- Latency overlay, random/bulk events, privacy masks, WebSocket live updates.

### v2.0 (P2)
- Profile G (edge recording + playback), Profile M (metadata), two-way audio.
- GPU encode, Docker/macvlan, network impairment, vendor emulation.

---

## 13. Feature Lock – Decisions Needed From You

Please confirm or change each item. After this, I will write the implementation plan in `plan/`.

1. **Addressing:** Port Mode in v1.0 and IP Mode in v1.1. Or do you need IP Mode in v1.0, because your target NVRs
   only accept port 80?
2. **Profiles:** S + T in v1.0, and G + M in v2.0. Is that OK?
3. **Scale:** is "~150 passthrough + ~10 encode cameras on one PC" enough, or do you need more?
4. **Per-camera web page:** is the menu in 7.2 the right depth, or should it be lighter?
5. **Platform:** Windows first (your dev machine), with Linux also supported. Is that OK?
6. **Target NVRs:** which NVRs must pass first, beyond Shah-NVR and ODM?
7. **Fault injection:** are the P0 faults (offline, stream drop, reboot) enough for v1.0?
8. **Default camera credentials:** `admin` / `admin123`, editable per camera and through bulk edit. Is that OK?
