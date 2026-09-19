# Architecture

```
Frontend (React) ──► FastAPI (/api/v1) ──┬──► App services (scheduling, booking, workflows, Q, notifications)
                                          └──► AI layer (LangGraph ─► MCP registry ─► same app services)
App services ──► Integration layer (EHRClient) ──► Mock EHR (separate container, replaceable)
Booking: create → EHR → VERIFY (re-read) → sync internal → confirm → workflows/notifications
Failure: timeout → status unknown_outcome → probe by idempotency key → found? sync : reconcile+escalate
```

## State separation
| Concern | Where |
|---|---|
| Business (appointments, doctors…) | PostgreSQL models (`models/`) |
| AI conversational vs transactional vs user vs workflow vs integration | `ai_contexts` columns, never one blob |
| Integration ops/verifications/reconciliation | `integration_operations`, `integration_verifications`, `reconciliation_records` |
| Workflow runs | `workflow_executions` |
| Observability | `audit_events`, `operational_events`, `capability_executions` — joined by `correlation_id` |

## Data model (core tables)
users, hospitals, departments, specialties, doctors, patients, user_context_prefs, calendars, availability_rules, blocked_slots, leaves, appointment_types, appointments (uq doctor+start), appointment_history, questionnaires, questionnaire_responses, workflows, workflow_executions, notifications, healthcare_connections, external_id_maps, integration_operations, integration_verifications, reconciliation_records, ai_conversations, ai_messages, ai_contexts, capability_defs, capability_executions, ai_evaluations, audit_events, operational_events.

## Tenant model
`users.hospital_id` binds staff; `tenant_hospital_id()` rejects cross-tenant claims; list endpoints scope by role; patients see only own rows; doctors only own appointments.

## Appointment flow (statuses)
```
pending → confirmed → rescheduled → confirmed → completed
   ↓          ↓            ↓              ↓           ↓
 failed   cancelled    cancelled      cancelled   (terminal)
   ↓          ↓
reconciliation_required → confirmed | cancelled | failed
```
- `pending` is a millisecond transit state (row created, EHR write in flight) — not an approval inbox. No human approval step exists by design.
- `confirmed` only after EHR read-back verification (`IntegrationVerification matched`).
- Terminal: `completed`, `no_show`, `cancelled`, `failed`. Re-entry only via `failed → requested` (retry as new booking).
- There is deliberately **no `rejected` row state**: a lost race keeps zero rows (loser rolls back). Rejection is a **coded response**, not stored data.

## Concurrency: two users, one slot (no DB locks)
Arbitration is atomic index checks at commit time — no `SELECT FOR UPDATE`, no advisory locks:
- `UNIQUE(doctor_id, starts_at)` blocks exact-start doubles; `EXCLUDE … tstzrange && WHERE active` blocks overlapping ranges. One committer wins, the other gets `IntegrityError` → rollback → `409 SLOT_TAKEN: …`.
- Same idempotency key → same row returned (`deduplicated`, never a second row). EHR-side 409 → also mapped to `SLOT_TAKEN`.
- Past starts → `400 SLOT_PAST`. Frontend renders “❌ Rejected — slot just taken” + next 3 free alternatives (one-tap rebook, fresh key).
