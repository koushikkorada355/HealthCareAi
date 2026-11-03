    # MediConnect — AI-Native Multi-Hospital Scheduling Platform
    ## Resume-Ready Project Documentation

    ### 1. Project Title
    **MediConnect — AI-Native Multi-Hospital Scheduling Platform**
    Alternative: `CareAccess — AI-Powered Healthcare Scheduling SaaS`

    ### 2. One-Line Pitch (Resume Heading)
    ```
    MediConnect – AI-native multi-hospital appointment scheduling platform (React + FastAPI + LangGraph + MCP + PostgreSQL + Docker)
    ```

    > Full-stack multi-tenant healthcare SaaS where patients book via AI chat + voice → real availability engine → EHR integration with verify-before-confirm reliability.

    ### 3. Short Summary (2-3 lines for resume)
    Built an AI-native, multi-tenant scheduling platform connecting Patients, Doctors, Hospital Admins, and Platform Admins. Implemented conversational AI booking via LangGraph + MCP (Mercury 2.5 + GPT-OSS fallback), real slot engine respecting working hours/blocks/leave/conflicts, and Mock EHR integration with verify-before-confirm, idempotency keys, and timeout → probe → sync recovery without double-booking. Fully Dockerized with 4 services.

    ### 4. Detailed Description (Portfolio / GitHub / Interview)

    This is not a CRUD app or chatbot demo. It is one coherent reliable workflow:

    ```
    Patient Request → AI Understanding → Hospital/Doctor Discovery → Real Availability → Authorized Booking → EHR Integration → External Verification → State Sync → Questionnaire + Workflow → Doctor/Admin Visibility
    + Timeout → Probe → Sync-without-duplicate recovery demo
    ```

    **4 user roles:**
    - **Patient:** register/login, AI chat + voice assistant, hospital/doctor discovery, real slot picker, book / reschedule / cancel, upcoming + history, conversational questionnaires, preferences, profile, reviews.
    - **Doctor:** today / upcoming / all appointments, calendar, availability + blocked time management, appointment detail with pre-visit answers, activity.
    - **Hospital Admin:** overview, profile, departments, specialties, doctors, schedules, appointments, questionnaire builder, integrations, workflows, notifications, reviews, analytics, activity, audit.
    - **Platform Admin:** dashboard, hospital applications (approve / reject / corrections / suspend / reactivate), hospitals, doctors, patients, appointments, AI activity, integration activity, workflow monitoring, analytics, AI evaluation, ops health, audit logs.

    **AI Core:**
    LangChain + LangGraph with explicit graph state + conditional routing.
    Nodes: intent detection, context retrieval, clarification, hospital discovery, doctor discovery, availability, patient selection, booking, verification, synchronization, questionnaire, workflow initiation, human escalation.
    AI never touches Postgres/EHR directly — only via typed MCP capabilities with validation, auth, idempotency, audit. Administrative-only, fail-closed safety — no diagnosis/prescription, returns 503 instead of hallucinating when LLMs are down.

    **17 MCP Capabilities include:**
    `search_hospitals`, `search_doctors`, `check_availability`, `lookup_patient`, `get_appointment`, `create_appointment`, `reschedule_appointment`, `cancel_appointment`, `get_questionnaire`, `submit_questionnaire`, `send_notification`, `start_workflow`, `get_context`, `update_preferences`, `verify_external_appointment`, `synchronize_state`, `transfer_to_human`

    **Scheduling Engine:**
    Central source of truth. Slot available only when: doctor active, calendar active, within working hours, not blocked, not on leave, not already booked, appointment-type compatible. Transactional conflict detection prevents concurrent double-booking. Revalidated immediately before booking. AI never invents slots.

    **Reliability / Distributed Systems:**
    Internal row stays `pending` while EHR write is in flight, `confirmed` only after read-back verification matches. Unknown outcomes probed by idempotency key — never blindly retried, never duplicated. Correlation IDs end-to-end across conversation → AI decision → capability → scheduling → EHR → verification → sync → workflow → notification. Reconciliation records + human escalation dashboard. Seeded `unknown_outcome` demo + `?fail=timeout` injection + `simulate: timeout_after_create` API path.

    **Voice v1:**
    Browser mic orb → POST /ai/stt (Groq whisper-large-v3-turbo) → normal AI chat graph → browser speechSynthesis TTS + cards. Mute toggle, barge-in on new tap/send, ~2s silence auto-stop, 60s max. No telephone in v1.

    **Workflows / Questionnaires / Notifications:**
    Booking fires `appointment.booked` → auto-assign questionnaire + patient/doctor notifications. Questionnaire assigned → patient answers conversationally → structured response → doctor reviews → completion workflow. Events, retries, idempotency, execution history, failure states tracked on dashboards.

    ### 5. Tech Stack

    | Layer | Choice |
    |---|---|
    | Frontend | React 18, Vite 6, Tailwind 3, react-router 6, recharts, react-markdown, Nginx |
    | Backend | FastAPI, SQLAlchemy 2, PostgreSQL 16, APScheduler, httpx, Pydantic 2, JWT + bcrypt |
    | AI | LangChain Core + LangGraph 0.2 + MCP registry, Inception Mercury 2.5 primary, Groq openai/gpt-oss-120b fallback |
    | Voice | Groq whisper-large-v3-turbo STT, browser speechSynthesis TTS |
    | Mock EHR | Separate FastAPI service behind connector, replaceable |
    | Infra | Docker + Docker Compose (postgres, mock-ehr, backend, frontend), persistent pgdata volume, healthchecks |
    | Testing | pytest (availability, slot validation, state transitions, verify-sync, double/overlap rejection, unknown-outcome recovery, AI routing, safety, typo repair) |

    Architecture:
    ```
    Patient browser → Frontend React → Backend FastAPI → AI: LangGraph + MCP → App services → Mock EHR
                                                            ↓
                                                          Postgres
    ```

    Docker services:
    - `postgres:16-alpine` — business DB, host port 5434
    - `careaccess-backend:local` (python:3.12-slim) — FastAPI + LangGraph + MCP, host port 8002
    - `careaccess-mock-ehr:local` (python:3.12-slim) — fake external system, host port 8001
    - `careaccess-frontend:local` (node:20-alpine build → nginx:alpine) — React SPA, host port 8080

    Run: `cp .env.example .env && docker compose up --build`

    ### 6. Key Features Built
    - Multi-tenant auth + RBAC + server-side tenant isolation (Hospital A never sees Hospital B)
    - Hospital onboarding lifecycle: Draft → Submitted → Under Review → Approved/Rejected + suspend/reactivate
    - Doctor lifecycle: Invited → Active → Inactive/Suspended, with external provider ID mapping
    - Appointment state machine: Requested, Pending, Confirmed, Rescheduled, Cancelled, Completed, No-show, Failed, Sync Pending, Reconciliation Required + full history + internal/external IDs
    - Questionnaire builder (yes/no, choice, multi-choice, numeric, date, short/long text) + conversational collection
    - Event-driven workflows with delays, conditions, retries, idempotency, execution history
    - Observability: AI metrics (latency, capability success, escalation, cost), scheduling metrics, integration metrics, workflow metrics, audit events, correlation IDs
    - Seed data: multiple hospitals/doctors/patients/appointments/slots/questionnaires/conversations/integrations (healthy/failed/timeout/unknown)/workflows/notifications/audit

    ### 7. Resume Bullets (Copy-Paste)

    * Architected multi-tenant SaaS backend in **FastAPI + PostgreSQL** with **25+ entities** (hospitals, doctors, calendars, appointments, questionnaires, workflows, integration ops, audit), server-side tenant isolation and RBAC for 4 roles.
    * Built **LangGraph AI agent (12+ nodes)** with **MCP tool registry (17 capabilities)**; enforced capability-based actions, clarification-over-guessing, and fail-closed safety, eliminating hallucinated slots.
    * Engineered **scheduling engine** respecting working hours, blocks, leave, and conflicts with transactional conflict detection; revalidated slots pre-booking to prevent concurrent double-booking.
    * Implemented **verify-before-confirm EHR integration** via replaceable connector to isolated Mock EHR service; added idempotency keys, correlation IDs, verification + sync, and timeout-probe-sync recovery with reconciliation dashboard.
    * Shipped **voice assistant (Groq Whisper STT + browser TTS)** reusing same chat graph, plus questionnaire/workflow automation (`appointment.booked` → auto-assign + notifications); containerized full stack in **Docker Compose** with one-command `up --build`, seed data, and in-container pytest suite.

    Skills tags: `React, FastAPI, PostgreSQL, LangChain, LangGraph, MCP, Docker, System Design, Distributed Reliability, RBAC, Voice AI`

    ### 8. Demo Script (5 min)
    1. Login as patient `aarav@example.org` → AI Assistant → "I need to see a doctor for my shoulder pain sometime this week." → intent trace + real doctor/slot options → Book → verified confirmation with correlation ID.
    2. Voice: same page → tap orb → speak → spoken verified reply.
    3. Upcoming → details → verification badge + timeline → questionnaire → fill conversationally.
    4. Doctor `doc0@example.org`: dashboard → today → open visit → pre-visit answers.
    5. Hospital admin `admin@citycare-general.org`: overview → integrations → AI activity → questionnaires.
    6. Failure demo: Platform admin `admin@gmail.com` → Reconciliation → Probe EHR + sync on seeded `unknown_outcome` record; no duplicate.
    7. Platform admin: Applications → approve `northgate-community` → ops wall, audit, analytics.

    Demo accounts: System Admin `admin@gmail.com / 12345`, others `password123`.

    ### 9. Interview Talking Point
    > "Hardest part was reliability, not chatbot. If EHR times out after creating, you can't just retry — you'll double-book. So I mark internal as pending, probe EHR by idempotency key, sync if found else retry safely. That plus verify-before-confirm was the core design."

    ### 10. Links
    - Frontend: http://localhost:8080
    - Backend docs: http://localhost:8002/docs
    - Mock EHR: http://localhost:8001/health
    - Docs: docs/ARCHITECTURE.md, docs/AI_USAGE.md, docs/PROMPTS.md, docs/DOCKER.md, docs/VOICE.md, docs/DEMO.md
