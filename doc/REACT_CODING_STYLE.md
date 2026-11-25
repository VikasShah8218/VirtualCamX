# My React Coding Style, Folder Layout and Tech Stack

A short guide to how I build React web apps. It is based on `nvr_client/` (the Shah-NVR web UI),
and I use the same pattern for new React apps. The backend guide is in [CODING_STYLE.md](CODING_STYLE.md).

---

## 1. Folder structure

```
nvr_client/
├── index.html
├── package.json
├── vite.config.ts           # Vite config (dev port 5180, "@" alias -> src/)
├── tsconfig*.json
├── components.json          # shadcn/ui config
├── branding.json            # app name / logo settings
├── openapi/                 # OpenAPI JSON exported from the FastAPI servers
│   ├── central.json
│   └── node.json
├── public/                  # static files (icons, images)
├── tests/                   # small unit tests for pure logic (*.test.ts)
│
└── src/
    ├── main.tsx             # starts React
    ├── App.tsx              # providers + all routes (pages are lazy-loaded)
    ├── index.css            # Tailwind + theme colors (CSS variables)
    │
    ├── api/                 # everything that talks to the backend
    │   ├── central.d.ts     # GENERATED types from central OpenAPI (do not edit)
    │   ├── node.d.ts        # GENERATED types from node OpenAPI (do not edit)
    │   ├── client.ts        # typed fetch clients, ApiError, unwrap()
    │   ├── queries.ts       # React Query hooks: useCameras(), useCreateCamera(), ...
    │   └── types.ts         # short type names taken from the generated types
    │
    ├── components/          # shared UI used by many pages
    │   ├── ui/              # shadcn/ui building blocks (button, dialog, table, ...)
    │   ├── layout/          # AppLayout (sidebar + header), nav.ts (menu items)
    │   └── CameraPicker.tsx, Pager.tsx, StatusBadge.tsx, ...
    │
    ├── features/            # one folder per screen / feature
    │   ├── cameras/
    │   │   ├── CamerasPage.tsx       # the page (list)
    │   │   ├── CameraDetailPage.tsx  # detail page with tabs
    │   │   ├── CameraFormSheet.tsx   # add/edit form
    │   │   └── VideoTab.tsx, DeviceTab.tsx, ...
    │   ├── live/            # LivePage, LivePlayer, PTZ, WebRTC (whep.ts)
    │   ├── playback/
    │   ├── nodes/
    │   └── ...
    │
    └── lib/                 # plain logic and helpers (no big UI)
        ├── auth/            # sign-in, session, permissions, RequirePerm
        ├── format.ts, time.ts, pager.ts, schedule.ts, ...
        ├── settings.tsx     # user settings (context provider)
        └── utils.ts         # cn() and small helpers
```

### Simple rules
- **One feature = one folder in `features/`.** Pages are named `XxxPage.tsx`; dialogs `XxxDialog.tsx`;
  side forms `XxxSheet.tsx`; tabs `XxxTab.tsx`.
- **Only `api/` talks to the server.** Pages never call `fetch` directly. They use hooks from
  `api/queries.ts`.
- **Shared UI goes in `components/`, plain logic goes in `lib/`.** Logic in `lib/` is easy to test
  because it has no UI.
- **Never edit generated files** (`central.d.ts`, `node.d.ts`). Regenerate them instead.
- **`@/` means `src/`**, e.g. `import { Button } from "@/components/ui/button"`.

---

## 2. Core technologies

| Technology | What I use it for |
|---|---|
| **React 19** | UI |
| **TypeScript** | Types everywhere |
| **Vite** | Dev server (`npm run dev`, port **5180**) and build |
| **React Router 7** | Pages and URLs |
| **TanStack React Query** | Loading, caching and refreshing server data; mutations |
| **openapi-typescript** + **openapi-fetch** | API types generated from FastAPI, so the client and server always match |
| **Tailwind CSS 4** | Styling |
| **shadcn/ui** + **Radix UI** | Ready-made, accessible components (dialogs, menus, tables, ...) |
| **lucide-react** | Icons |
| **sonner** | Toast messages (success / error) |
| **Recharts** | Charts (CPU, memory, storage) |
| **date-fns** + **react-day-picker** | Dates and date pickers |
| **hls.js** + **WebRTC (WHEP)** | Video playback: recorded (HLS) and live |
| **oxlint** | Linting (`npm run lint`) |
| **node:test** | Small unit tests (`npm run test:<name>`) |

---

## 3. Coding style

- **Function components and hooks only.** No class components.
- **Named exports** (`export function CamerasPage()`), not default exports. Only `App` is a default export.
- **Server data lives in React Query**, not in `useState`. Use `useState` only for local UI state
  (open dialog, form fields, selected tab).
- **One hook per API call** in `queries.ts`: `useXxx()` for reading, `useCreateXxx()` / `useUpdateXxx()`
  for changes. Mutations show a toast and refresh the related queries.
- **Errors:** API calls go through `unwrap()`, which throws an `ApiError` carrying the server's message.
  The user sees that message in a toast.
- **Pages are lazy-loaded** in `App.tsx`, so each page is its own small file in the build.
- **Permissions:** routes are wrapped in `<RequirePerm>`; buttons hide when the user lacks the right.
- **Styling:** Tailwind classes plus `cn()` to merge them. Colors come only from theme variables
  (`bg-background`, `text-foreground`, `bg-card`), never hard-coded hex codes in components.
- **Theme: "Dusk slate":** a soft dark close to light, never pure black (`--background: #2e3440`).
- **Comments explain *why*,** not what.

---

## 4. Everyday commands

```bash
cd nvr_client
npm install           # first time
npm run dev           # http://localhost:5180
npm run build         # type-check + production build
npm run lint
npm run test:pager    # run one test file

# After a backend API change:
py ../tools/export_openapi.py   # FastAPI -> openapi/*.json
npm run gen:api                 # openapi/*.json -> src/api/*.d.ts
```
