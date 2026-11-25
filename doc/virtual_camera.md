# IP Camera Software – Competitive Feature Draft

**Version:** 0.1 (Draft)
**Scope:** Camera firmware/software only (web UI, video pipeline, analytics, security, integrations, management). Hardware is out of scope.
**Priority key:**
- **P0** – Must-have to be competitive / sellable
- **P1** – Expected in a modern mid–high tier camera
- **P2** – Differentiator / future roadmap

---

## 1. Product Goals

1. **Secure by default.** Meet modern regulations (EU CRA, UK PSTI, India STQC/ER) with no extra configuration.
2. **AI at the edge.** Classify people and vehicles on the camera itself, with far fewer false alarms than pixel-based motion detection.
3. **Open and interoperable.** Work with every major VMS/NVR through ONVIF, RTSP, and a clean REST API.
4. **Simple to install and manage.** Fast first-time setup, bulk management, and safe OTA updates.
5. **Efficient.** Smart codecs that cut bandwidth and storage by 50% or more without visible quality loss.

---

## 2. Current Baseline (from existing firmware)

| Area | Already present | Gap / Improvement |
|---|---|---|
| Video | 3 streams, H.265, up to 5MP@25fps, CBR/VBR, Smart Stream, I-frame interval | Smart Stream defaults to **Off**; no AV1; no dynamic GOP visibility; no per-stream bitrate preview |
| Image | Day/Night auto with thresholds, Smart IR, Corridor mode, Rotation, OSD, Privacy Mask, ROI | No WDR scheduling profiles, no scene presets, no live before/after preview |
| Events | Grid-based Motion Detection, Audio alarm, I/O, Exception | Grid drawing is outdated; motion is pixel-based (no object filtering) |
| VCA | Region Entrance/Exit, Advanced Motion, Tamper, Line Crossing, Loitering, Object Left/Removed (Human/Vehicle filter) | No polygon editor with multi-zone, no AI attributes, no metadata streaming, no natural-language search |
| Other | People Counting, Face Detection, Heat Map | No dashboards or reports, no data export API |
| UI | Classic multi-page web UI with per-page Save | Needs a modern responsive UI and a guided setup wizard |

---

## 3. Video & Streaming

| # | Feature | Description | Priority |
|---|---|---|---|
| 3.1 | Multi-stream | Primary, secondary, and tertiary streams plus an optional dedicated mobile/low-bandwidth stream | P0 |
| 3.2 | Codecs | H.264, H.265, MJPEG; **AV1** (if the SoC supports it) for future-proofing | P0 / P2 |
| 3.3 | Smart Codec 2.0 | Dynamic GOP, dynamic ROI, and scene-adaptive bitrate. Higher quality on moving objects, lower on static background. **ON by default** | P0 |
| 3.4 | Bitrate modes | CBR, VBR, and Capped VBR with quality level (1–10) | P0 |
| 3.5 | Bitrate estimator | Live display of actual bitrate plus estimated storage per day/week per stream | P1 |
| 3.6 | Zipstream-like event boost | Raise quality automatically while an event is active | P1 |
| 3.7 | Corridor & rotation | 90/180/270° rotation, mirror, flip | P0 (exists) |
| 3.8 | Digital zoom & ePTZ | Crop-and-stream virtual views from a high-resolution sensor | P1 |
| 3.9 | Dewarping | For fisheye lenses: on-camera dewarp modes (panorama, quad, double panorama) | P2 |
| 3.10 | Low-latency streaming | WebRTC for browser live view with sub-500 ms latency, no plugins | P0 |
| 3.11 | Protocols | RTSP/RTP (UDP/TCP/HTTP tunnel), RTSPS, RTMP push, SRT, HLS, multicast | P0 / P1 |
| 3.12 | Snapshot API | JPEG snapshot by URL, on schedule, or on event | P0 |
| 3.13 | Corridor-optimized streams | Automatic 9:16 stream variants | P2 |
| 3.14 | Text & graphic OSD | Multiple text lines, logo upload, dynamic fields (date, temperature, event, counter values) | P1 |
| 3.15 | Debug overlay toggle | Move the current on-video debug info (codec, Smart Stream, connections) to an "Engineering overlay" toggle that is off by default | P0 |

---

## 4. Image Settings

| # | Feature | Description | Priority |
|---|---|---|---|
| 4.1 | Scene presets | One click: Indoor, Outdoor, Parking, Traffic/LPR, Retail, Low-light | P1 |
| 4.2 | Exposure control | Auto, manual, shutter priority, max shutter limit (important for motion blur and LPR) | P0 |
| 4.3 | WDR / HLC / BLC | With strength levels and region-based BLC | P0 |
| 4.4 | Day/Night | Auto, schedule, external input, and API-triggered; hysteresis thresholds | P0 (exists) |
| 4.5 | Smart IR / anti-overexposure | Automatic IR balancing for close objects | P0 (exists) |
| 4.6 | 3D-DNR, defog, EIS | Noise reduction, digital defog, electronic image stabilization | P1 |
| 4.7 | Image profiles by schedule | Different image settings for day, night, or custom time ranges | P1 |
| 4.8 | Live A/B preview | Side-by-side preview while changing settings before saving | P2 |
| 4.9 | Privacy masks | Polygon masks (≥8), mosaic or solid, and **dynamic AI privacy masking** that auto-blurs faces and people | P0 / P2 |
| 4.10 | Focus assist | Focus peaking or a sharpness score during installation | P1 |

---

## 5. Edge AI & Video Analytics

### 5.1 Core Detection Engine (P0)
- Deep-learning object classification: **Human, Vehicle (car/bus/truck/bike/motorbike)**, plus "unknown" filtering.
- Pixel-based motion is kept only as a legacy fallback.
- AI-filtered motion with a false-alarm filter that ignores rain, leaves, shadows, headlights, and animals.
- Configurable confidence threshold per rule.
- Min/max object size filter drawn on the live view (already partially present).

### 5.2 Rule-Based Analytics

| Rule | Notes | Priority |
|---|---|---|
| Intrusion (region entrance/exit/inside) | Polygon zones (≥8 points), up to 8 zones, per-zone schedule | P0 |
| Line crossing | Directional (A→B, B→A, both), multiple lines | P0 |
| Loitering | Dwell-time threshold per zone | P0 |
| Object left / removed | Unattended bag, asset removal | P1 |
| Tamper detection | Covered, defocused, moved, sprayed | P0 |
| Crowd / occupancy | Live occupancy count with threshold alarms | P1 |
| Queue management | Queue length and wait time | P1 |
| People counting | In/out lines, daily/weekly reports, CSV export | P1 (exists, enhance) |
| Heat map | Time-based and dwell heat maps with exportable images | P1 (exists, enhance) |
| Wrong-way / U-turn / illegal parking | Traffic use cases | P2 |
| Fall / slip detection | Healthcare, elderly care | P2 |
| Fire / smoke detection (visual) | Early warning, not a replacement for certified alarms | P2 |
| Audio analytics | Scream, glass break, gunshot, sound-level threshold | P1 |

### 5.3 Object Attributes (P1)
- **Person:** upper/lower clothing color, bag, hat/helmet, mask, gender/age range (configurable; off by default where privacy laws apply).
- **Vehicle:** type, color, direction, speed estimate (P2).
- **PPE detection:** helmet and vest (industrial).

### 5.4 License Plate Recognition (P2)
- Indian, EU, and US plate formats; allow/block lists; gate control via relay output.

### 5.5 Face Detection / Recognition (P2)
- Face detection with best-shot capture (exists, enhance).
- Face recognition only behind an explicit opt-in, with an on-camera database, consent and retention controls, and a legal notice. This is a high regulatory risk.

### 5.6 Smart Search & Metadata (Differentiator)
- **ONVIF Profile M metadata stream** with bounding boxes, class, and attributes.
- Forensic search: "Show people in red shirts crossing Line 1 yesterday."
- **Natural-language search (P2):** an on-device or VMS-side vision-language model for plain-language video search and event descriptions.
- Event thumbnails and short clips attached to every alarm.

### 5.7 AI App Platform (P2)
- SDK/container runtime so partners can deploy custom models or apps, similar to Axis ACAP or Hanwha Wisenet open platform.
- Model update path separate from firmware updates.

### 5.8 Analytics UX Requirements
- Draw polygons, lines, and size boxes directly on live video. **Replace the current grid-based motion editor.**
- Show real-time bounding boxes and rule triggers on live view ("test mode").
- Merge "Motion Detection" (Basic Event) and "Advanced Motion Detection" (VCA) into one AI Motion page with a "Legacy pixel mode" option.

---

## 6. Events & Actions

### 6.1 Triggers
- Analytics rules, motion, audio, digital input, tamper, network loss, IP conflict, storage full/fail, illegal login, temperature/health warnings, scheduled time, API/webhook trigger.

### 6.2 Actions

| Action | Priority |
|---|---|
| Record to SD/NAS (with pre/post buffer) | P0 |
| Snapshot to FTP/SFTP/email/NAS | P0 |
| HTTP(S) webhook (custom URL, headers, JSON template) | P0 |
| MQTT publish (event plus metadata) | P1 |
| Relay/alarm output | P0 |
| Play audio clip / voice-down on speaker (deterrence) | P1 |
| Strobe/light trigger (if hardware allows) | P1 |
| Push notification (mobile app) | P1 |
| PTZ preset (for PTZ models) | P1 |
| Trigger another camera (peer-to-peer) | P2 |

### 6.3 Event Engine
- **Rule builder:** IF trigger AND condition (schedule, input state, day/night) THEN actions.
- Arm/disarm schedules plus a manual "privacy mode" toggle.
- Event cooldown and de-duplication.
- Searchable event log with thumbnails, exportable as CSV/JSON.

---

## 7. Recording & Storage

| # | Feature | Priority |
|---|---|---|
| 7.1 | Edge recording to microSD (continuous, event, schedule) | P0 |
| 7.2 | Network storage: NAS via SMB/NFS | P1 |
| 7.3 | **ANR (Automatic Network Replenishment):** record locally during network loss, backfill the NVR/VMS later | P1 |
| 7.4 | Loop overwrite and retention by days | P0 |
| 7.5 | SD card health monitoring with wear and failure alerts | P1 |
| 7.6 | Encrypted storage of recordings | P1 |
| 7.7 | Web playback timeline with event markers, speed control, clip export (MP4) | P0 |
| 7.8 | **Signed video export** (tamper-evident, verifiable) | P1 |
| 7.9 | ONVIF Profile G (edge storage and retrieval) | P1 |

---

## 8. Audio

| # | Feature | Priority |
|---|---|---|
| 8.1 | Codecs: G.711, G.726, AAC, Opus | P0 |
| 8.2 | Two-way audio (web and app) | P1 |
| 8.3 | Noise suppression, echo cancellation | P1 |
| 8.4 | Audio clip library for event playback | P1 |
| 8.5 | Audio analytics (see 5.2) | P1 |
| 8.6 | Audio recording legal toggle (off by default in regions requiring consent) | P0 |

---

## 9. Network & Connectivity

| # | Feature | Priority |
|---|---|---|
| 9.1 | IPv4/IPv6, DHCP, static, link-local fallback | P0 |
| 9.2 | DNS, NTP (with NTS where possible), DDNS | P0 |
| 9.3 | UPnP / mDNS / WS-Discovery (each toggleable, secure defaults) | P0 |
| 9.4 | QoS / DSCP tagging | P1 |
| 9.5 | 802.1X (EAP-TLS, PEAP) | P1 |
| 9.6 | SNMP v3 (v1/v2 disabled by default) | P1 |
| 9.7 | SMTP with TLS; OAuth for Gmail/Outlook | P1 |
| 9.8 | Cloud P2P connectivity (no port forwarding) | P1 |
| 9.9 | VLAN tagging | P2 |
| 9.10 | Bandwidth limiter (total egress cap) | P1 |

---

## 10. Cybersecurity (Top Priority)

### 10.1 Authentication & Access
- **No default passwords.** Force a strong password at first boot (required by UK PSTI and EU CRA).
- Role-based access control: Admin, Operator, Viewer, plus custom roles.
- Account lockout and brute-force protection with configurable thresholds.
- Multi-factor authentication (TOTP) for web admin (P1).
- Digest authentication by default; basic auth disabled.
- Session timeout and concurrent session limits.
- Optional SSO via OIDC/SAML for enterprise (P2).

### 10.2 Transport & Data
- HTTPS by default with HTTP redirect; TLS 1.2+ (prefer 1.3); weak ciphers disabled.
- Certificate management: self-signed, CSR, import, **automatic renewal (ACME/EST)** (P1).
- RTSPS / SRTP for encrypted video.
- Encrypted configuration backups.

### 10.3 Firmware & Platform
- **Signed firmware** with verification before install; reject unsigned or downgraded images.
- Secure boot chain and A/B partition rollback (software side).
- Disable unused services (Telnet off, SSH off by default with audit logging when enabled).
- IP filtering (allow/deny lists).

### 10.4 Monitoring & Lifecycle
- Security audit log (logins, config changes, firmware updates) with syslog over TLS export.
- **SBOM** published per firmware release.
- Vulnerability disclosure policy and PSIRT process; defined security support period per model.
- Security dashboard page that scores the camera's current config (e.g., "SNMPv2 enabled – risk").

### 10.5 Compliance Targets
- **EU Cyber Resilience Act:** vulnerability reporting obligations and full compliance timeline.
- **UK PSTI Act:** no universal default passwords, vulnerability reporting contact, support-period statement.
- **ETSI EN 303 645** (consumer IoT baseline).
- **India:** MeitY Essential Requirements for CCTV / STQC testing under BIS compulsory registration.
- **US:** NDAA Section 889 (mainly component sourcing) and the FCC Cyber Trust Mark (optional).
- **ONVIF security:** compliant with ONVIF security service where applicable.
- Optional: FIPS 140-3 validated crypto module for government projects (P2).

---

## 11. Privacy Features

- Static and AI-based dynamic privacy masking (faces, bodies, plates).
- Per-feature privacy toggles (face attributes, audio, recognition) with region-based defaults.
- Data retention policies with auto-delete.
- "Privacy shutter" mode: stop streaming and recording on schedule or API call.
- Export redaction: blur faces in exported clips (P2).
- Privacy settings page that shows in plain language what is being collected.

---

## 12. Web UI / UX Redesign

| # | Feature | Priority |
|---|---|---|
| 12.1 | **First-boot wizard:** password, network, time zone, language, stream preset, storage | P0 |
| 12.2 | Responsive UI that works on tablet and mobile browsers | P0 |
| 12.3 | **No plugins:** WebRTC/HTML5 live view and playback | P0 |
| 12.4 | Global "unsaved changes" bar instead of Save on every tab | P1 |
| 12.5 | Search box for settings ("bitrate", "IR") | P1 |
| 12.6 | Dark/light theme | P2 |
| 12.7 | Contextual help tooltips for every setting | P1 |
| 12.8 | Live preview next to every image or analytics setting | P0 |
| 12.9 | Dashboard home: health, storage, bitrate, recent events, security score | P1 |
| 12.10 | Multi-language (English, Hindi, plus key export markets) | P1 |
| 12.11 | Accessibility (keyboard navigation, contrast) | P2 |

**Suggested new menu structure:**
```
Dashboard
Live View
Playback & Search
Video & Audio
  ├─ Streams
  ├─ Image
  ├─ Overlay & Privacy
  └─ Audio
Analytics (AI)
  ├─ Detection Rules
  ├─ Counting & Occupancy
  ├─ Heat Map
  └─ Smart Search
Events & Actions
Storage
Network
Security
Integrations (ONVIF, API, MQTT, Webhooks, Cloud)
System & Maintenance
```

---

## 13. Integrations & Standards

| # | Item | Priority |
|---|---|---|
| 13.1 | ONVIF Profile S (streaming) | P0 |
| 13.2 | ONVIF Profile T (H.265, advanced streaming, events) | P0 |
| 13.3 | ONVIF Profile G (edge storage) | P1 |
| 13.4 | ONVIF Profile M (analytics metadata) | P1 |
| 13.5 | Certified VMS drivers: Milestone XProtect, Genetec, Nx Witness, plus your own NVR | P1 |
| 13.6 | **REST/JSON API** (OpenAPI spec, token auth) covering every UI setting | P0 |
| 13.7 | Webhooks and MQTT | P0 / P1 |
| 13.8 | Home and smart-building integrations (optional SKU) | P2 |
| 13.9 | Access-control and alarm-panel integration via I/O and API | P1 |

---

## 14. Cloud & Mobile (Optional Service Layer)

- Cloud-connected device management (enable/disable per install; off by default for enterprise).
- Mobile app: live view, playback, push alerts with snapshots, two-way audio, quick share clip.
- Cloud recording tier (subscription), event clips only or continuous.
- Remote firmware updates and config templates across sites.
- Multi-site / multi-tenant portal for installers and integrators (P2).

---

## 15. Device Management & Maintenance

| # | Feature | Priority |
|---|---|---|
| 15.1 | Firmware update via web, API, and bulk tool; **A/B partition with auto-rollback** | P0 |
| 15.2 | Config backup and restore (encrypted, JSON export) | P0 |
| 15.3 | Factory reset (soft, keep network) and hard reset | P0 |
| 15.4 | Scheduled reboot | P1 |
| 15.5 | Health monitoring: CPU, memory, temperature, uptime, stream clients, SD health | P1 |
| 15.6 | System log, diagnostic bundle download (one click for support) | P0 |
| 15.7 | Bulk discovery and config tool (desktop/web) | P1 |
| 15.8 | Remote syslog and SNMP traps | P1 |
| 15.9 | Watchdog and self-recovery for crashed services | P0 |

---

## 16. Release Roadmap (Suggested)

### MVP (v1.0)
- All **P0** items in streaming, security, events, storage, and UI.
- Basic AI: human/vehicle classification, intrusion, line crossing, tamper.
- ONVIF S/T, REST API, webhooks.
- First-boot wizard and secure defaults.

### v1.5
- Smart Codec 2.0 tuning, ANR, signed video.
- People counting and occupancy reports, heat map improvements.
- MQTT, ONVIF G/M, VMS integrations.
- Mobile app and P2P cloud.

### v2.0
- Object attributes and smart forensic search.
- Audio analytics, PPE, queue management.
- AI app platform / SDK.
- Natural-language search, dynamic privacy masking, LPR.

---

## 17. Open Questions

1. Which SoC is targeted? This decides NPU capacity (TOPS), AV1 support, and which AI models fit.
2. Target market: consumer, SMB, enterprise, or government? This changes cloud defaults and the compliance scope.
3. Own NVR/VMS, or third-party integration first?
4. Cloud service: in-house or partner platform?
5. Which export markets come first (India, EU, US, Middle East)? This drives the certification order.
6. Licensing model for advanced AI features: included, or paid license keys?

---

## 18. Competitive Reference (for benchmarking)

Benchmark feature parity against current lines from: **Axis, Hanwha Vision (Wisenet), Hikvision, Dahua, Uniview, Bosch, i-PRO, Verkada, CP Plus, Matrix.**
Key differentiators to beat: false-alarm rate, ease of setup, security posture, open API quality, and smart search.