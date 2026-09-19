# MediConnect — AI-Native Multi-Hospital Scheduling Platform

One coherent healthcare SaaS: **Patient request → AI understanding → real availability → authorized MCP action → EHR integration → external verification → sync → questionnaire → workflow → doctor/admin visibility**, plus a visible **timeout → probe → sync-without-duplicate** recovery demo.

## Stack
- **Frontend:** React 18 + Vite + Tailwind (`frontend/`)
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL (`backend/app/`)
- **AI:** LangChain + LangGraph (modular graph) + MCP capability registry + Grok (OpenAI-compatible, graceful fallback to deterministic rules)
- **Voice:** browser Web Speech default; server STT/TTS behind pluggable interface (`VOICE_*`)
- **Mock EHR:** separate FastAPI service (`mock-ehr/`) behind `EHRClient` connector — swappable for a real vendor
- **Infra:** Docker Compose (postgres volume, healthchecks, `depends_on`)

## Requirements (host) — Docker-only, nothing else installed

| Requirement | Version | Why |
|---|---|---|
| Docker Engine | 24+ | Runs every service in containers |
| Docker Compose | v2 (`docker compose version`) | Orchestrates the stack |
| Free RAM / disk | 4 GB RAM, ~3 GB disk | Images + postgres volume |
| Free ports | 8080, 8002, 8001, 5434 | Frontend, backend, mock-EHR, postgres (override via `FRONTEND_PORT` / `BACKEND_PORT` / `POSTGRES_PORT`) |

No Python, Node, or PostgreSQL on the host. All dependencies live inside images.

## Images

| Image | Source | Used by |
|---|---|---|
| `postgres:16-alpine` | Docker Hub (pulled) | `postgres` service — business database |
| `python:3.12-slim` | Docker Hub (pulled) | Base for locally-built `careaccess-backend` and `careaccess-mock-ehr` |
| `node:20-alpine` | Docker Hub (pulled) | Build stage of `careaccess-frontend` (compiles React/Vite) |
| `nginx:alpine` | Docker Hub (pulled) | Runtime stage of `careaccess-frontend` (static serve + `/api` proxy) |
| `careaccess-backend:local` | Built from `backend/Dockerfile` | FastAPI + LangGraph + MCP |
| `careaccess-mock-ehr:local` | Built from `mock-ehr/Dockerfile` | Fake external health system |
| `careaccess-frontend:local` | Built from `frontend/Dockerfile` | React SPA via nginx |

Full service/port/env reference: [`docs/DOCKER.md`](docs/DOCKER.md).

## Quickstart (Docker — the standard flow)
```bash
cp .env.example .env        # add GROK_API_KEY to enable Grok wording
docker compose up --build
```
| Service | URL |
|---|---|
| Frontend | http://localhost:8080 |
| Backend API + docs | http://localhost:8002/docs |
| Mock EHR | http://localhost:8001/health |

DB persists in `pgdata` volume. Backend auto-creates tables and seeds on first boot (`SEED_ON_STARTUP=true`).

## Demo accounts (password `password123`)
| Role | Email |
|---|---|
| Platform admin | admin@platform.org |
| Hospital admin | admin@citycare-general.org |
| Doctor | doc0@example.org |
| Patient | aarav@example.org |

## 5-minute demo script
1. **Login as patient** → AI Assistant → send *"I need to see a doctor for my shoulder pain sometime this week."* → see intent trace + real doctor/slot options → **Book** → verified confirmation with correlation ID.
2. **Voice**: open Voice tab → tap orb → speak → spoken verified reply.
3. **Appointment**: Upcoming → details → verification badge + history timeline → questionnaire → fill conversationally.
4. **Doctor** (`doc0`): dashboard → today → open visit → pre-visit answers.
5. **Hospital admin**: overview → integrations → AI activity → questionnaires.
6. **Failure demo**: Platform admin → Reconciliation → *Probe EHR + sync* on the seeded `unknown_outcome` record; or book via API with `"simulate":"timeout_after_create"` and watch probe → sync, no duplicate. See `docs/DEMO.md`.
7. **Platform admin**: Applications → approve `northgate-community` → ops wall, audit, analytics.

## Key rules enforced
- AI never touches Postgres/EHR directly — only via 17 typed MCP capabilities (`GET /api/v1/mcp/tools`).
- Slots only from the scheduling engine (working hours, blocks, leave, conflicts, active doctor/calendar).
- No "confirmed" before external verification; unknown outcomes are probed by idempotency key, never blindly retried.
- Tenant isolation server-side (`tenant_hospital_id` + per-query scoping).
- AI is administrative: diagnosis/prescription requests get a safe refusal + escalation offer.

## Docs
- `docs/DOCKER.md` — host requirements, image list, services/ports, Docker-only commands
- `docs/ARCHITECTURE.md` — layers, data model, booking/verify/recovery sequences, tenant model
- `docs/AI_DOCS.md` — graph nodes, prompts, Grok setup, evaluation
- `docs/DEMO.md` — click-by-click demo + failure scenario
- `.env.example` — all config; never commit `.env`
# HealthCareAi
