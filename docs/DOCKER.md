# Docker Reference — requirements, images, services, operations

Everything runs in Docker. The host needs **only** Docker Engine 24+ and
Compose v2 — no Python, Node, or PostgreSQL installed locally.

## 1. Host requirements

| Requirement | Minimum | Check command |
|---|---|---|
| Docker Engine | 24+ | `docker --version` |
| Docker Compose | v2 | `docker compose version` |
| RAM / disk | 4 GB RAM, ~3 GB free disk | — |
| Ports free | 8080, 8002, 8001, 5434 | — |

## 2. Images

### Pulled from Docker Hub (automatic on first `up --build`)

| Image | Size (approx) | Purpose |
|---|---|---|
| `postgres:16-alpine` | ~240 MB | PostgreSQL 16 database server |
| `python:3.12-slim` | ~130 MB | Base layer for backend + mock-ehr builds |
| `node:20-alpine` | ~170 MB | Build stage: `npm install` + `vite build` |
| `nginx:alpine` | ~40 MB | Runtime stage: serves SPA, proxies `/api` |

### Built locally from this repo

| Image | Dockerfile | Contents |
|---|---|---|
| `careaccess-backend:local` | `backend/Dockerfile` | Python deps (`requirements.txt`: fastapi, uvicorn, sqlalchemy, langchain, langgraph, mcp…) + `app/` |
| `careaccess-mock-ehr:local` | `mock-ehr/Dockerfile` | Python deps (fastapi, uvicorn) + `app.py` |
| `careaccess-frontend:local` | `frontend/Dockerfile` | Compiled `dist/` on nginx + `nginx.conf` proxy |

## 3. Services (`docker-compose.yml`)

| Service | Container port | Host URL | Depends on | Data |
|---|---|---|---|---|
| `postgres` | 5432 | `localhost:5434` (override: `POSTGRES_PORT=5435`) | — | `careaccess-pgdata` volume (survives restarts) |
| `mock-ehr` | 8001 | http://localhost:8001/health | — | in-memory demo store |
| `backend` | 8000 | http://localhost:8002/docs (override: `BACKEND_PORT=8010`) | postgres + mock-ehr healthy | tables auto-created; seeds when `SEED_ON_STARTUP=true` |
| `frontend` | 80 | http://localhost:8080 (override: `FRONTEND_PORT=8090`) | backend | stateless |

Internal traffic uses the `care-net` bridge network
(`backend → postgres:5432`, `backend → mock-ehr:8001`,
`frontend(nginx) → backend:8000`). Secrets come from `.env`
(see `.env.example`) — never baked into images.

## 4. Everyday commands (all Docker, host stays clean)

```bash
cp .env.example .env            # once; add GROK_API_KEY to enable Grok wording
docker compose up --build       # start everything (first run builds images)
docker compose up --build -d    # same, in background
docker compose ps               # status + health
docker compose logs -f backend  # follow backend logs
docker compose down             # stop (database volume kept)
docker compose down -v          # stop AND delete database (fresh seed next boot)

# Run the test suite inside the backend container (no host pytest):
docker compose run --rm backend pytest -q

# Re-seed demo data inside the running stack:
docker compose exec backend python -c "from app.db.session import SessionLocal; from app.db.seed import run; run(SessionLocal())"

# Production overlay (no seed, no dev ports):
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

## 5. Dockerfiles

- `backend/Dockerfile` — `python:3.12-slim`, pip install from
  `requirements.txt`, `HEALTHCHECK` on `/health`, serves port 8000.
- `mock-ehr/Dockerfile` — minimal `python:3.12-slim` + fastapi/uvicorn,
  serves port 8001.
- `frontend/Dockerfile` — multi-stage: `node:20-alpine` builds the SPA,
  `nginx:alpine` serves it with `nginx.conf` proxying `/api/*`, `/health`,
  `/docs` to the backend container.
- Each build context has a `.dockerignore` (no `node_modules`, `__pycache__`,
  `.env`, or local venvs leak into images or slow down builds).
