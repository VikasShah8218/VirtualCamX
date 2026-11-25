# My Coding Style, Folder Layout and Tech Stack

A short guide to how I build backend services. It applies to Shah-NVR
(`central_manager`, `media_node`) and to any new FastAPI service I start.

---

## 1. FastAPI server folder structure

Every Python service uses the same layout:

```
<service_name>/
├── main.py                 # entry point: builds the FastAPI app, starts it (py main.py)
├── .env                    # real settings (git-ignored), next to main.py
├── .env.example            # the same keys with safe sample values (committed)
├── requirements.txt
├── pytest.ini
│
├── settings/
│   └── settings.py         # one pydantic BaseSettings class that reads .env
│
├── database/
│   └── config.py           # TORTOISE_ORM dict (DB url + list of model modules)
│
├── migrations/             # Aerich migrations (only services with PostgreSQL)
│
├── utilities/              # small shared helpers used by many apps
│   ├── common.py           # utcnow(), run_periodic(), ...
│   └── pagination.py
│
├── app/                    # one folder per feature ("app")
│   ├── cameras/
│   │   ├── router.py       # API endpoints (APIRouter)
│   │   ├── models.py       # Tortoise models (DB tables)
│   │   ├── schemas.py      # Pydantic request/response models
│   │   ├── services.py     # business logic (the real work)
│   │   └── utils.py        # small helpers only for this app
│   ├── nodes/
│   ├── recordings/
│   └── ...
│
└── tests/                  # pytest tests
```

### Simple rules
- **One feature = one folder in `app/`.** Inside it: `router.py`, `models.py`, `schemas.py`,
  and `services.py` and/or `utils.py`. Only create the files the feature needs.
- **Routers stay thin.** They check input, call a service, and return a schema.
  The logic goes in `services.py`.
- **`main.py` only wires things together:** logging, DB registration, routers, CORS,
  and background loops (inside the `lifespan` function).
- **Settings come only from `settings.settings`.** No `os.getenv` scattered in the code.
- **Run every service the same way:** `workon nvr` then `py main.py` from the service folder.

### The two Shah-NVR servers

| | `central_manager/` (main server) | `media_node/` (recording/streaming server) |
|---|---|---|
| Port | 8000 | 7100 |
| Database | PostgreSQL (Tortoise + Aerich) | Its own SQLite file (`generate_schemas=True`) |
| Job | Camera/node registry, scheduler, failover, recording catalog, live/HLS URLs | Pulls cameras, records fMP4 chunks, serves video, ONVIF |
| Touches video? | **Never** | Yes |
| Touches PostgreSQL? | Yes | **Never** |
| Extra pieces | `app/auth/` (sign-in through the Auth Server) | `bin/` (MediaMTX), `app/onvif/`, `app/storage/` |

---

## 2. Core technologies

| Technology | What I use it for |
|---|---|
| **Python 3** | All backend services and the desktop app |
| **FastAPI** + **Uvicorn** | REST APIs and WebSockets, async everywhere |
| **Pydantic v2** / **pydantic-settings** | Request/response schemas and `.env` settings |
| **PostgreSQL** | Main database (central manager) |
| **SQLite** | Small local database for each media node, and quick tests |
| **Tortoise ORM** | Async ORM for all DB access |
| **Aerich** | Database migrations for Tortoise |
| **Argon2** | Password hashing (in my Auth Server) |
| **JWT / OAuth 2.1 / OIDC** | Sign-in through my own Auth Server (`AUTH_ENABLED`, `AUTH_PROVIDER`) |
| **Redis** | Cache and shared state: token versions, service tokens (Auth Server; planned for central auth state) |
| **Kafka** | Event streaming between services (planned for large scale) |
| **Docker** | Packaging and running services (planned: Docker images) |
| **httpx** | Async HTTP calls between services |
| **MediaMTX** | RTSP/HLS/WebRTC media server on each node |
| **React 19 + TypeScript** | Web client (`nvr_client`) |
| **PySide6 (QML) + libmpv** | Desktop client (`nvr_desktop`) |
| **pytest** | Tests |
| **virtualenvwrapper-win** | Python env: `workon nvr` |

---

## 3. Coding style

- **Async first.** Endpoints, DB calls and HTTP calls are `async`.
- **Type hints everywhere** (`str | None`, `list[int]`, `Literal[...]`).
- **Clear names.** `create_camera_with_streams`, `node_health_tick`, `retention_tick`.
- **Enums for states** (`class StreamStatus(str, Enum)`), not loose strings.
- **Comments explain *why*,** not what. Long design reasons go in `docs/`, and the comment points there.
- **Background jobs** use one helper, `run_periodic(name, interval, func)`. A failure is logged and
  never stops the loop.
- **Logging** uses `logging.getLogger("<service>")`. No `print`.
- **API paths are versioned:** `/api/v1/...`. Internal node↔central calls use separate `internal_router`s.
- **Times are UTC** (`utcnow()`, `use_tz=True`).
- **Secrets are never committed.** They live in `.env` files and the git-ignored `environment.local.md`.
- **After an API change:** `py tools/export_openapi.py`, then `npm run gen:api` in the client.
- **After a model change:** `aerich migrate --name <x>` then `aerich upgrade`.
- **Every feature change** is also recorded in `docs/FEATURES.md`.
