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

## Double-booking protection
DB unique `(doctor_id, starts_at)` + `validate_slot` re-check inside booking transaction + EHR-side conflict check + idempotency keys end-to-end (client → appointment → EHR → probe).
