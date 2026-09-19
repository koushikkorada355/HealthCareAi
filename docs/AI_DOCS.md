# AI Documentation

## Graph (`app/ai/graph.py`)
Nodes: `interpret` (intent + specialty + date-pref) → `clarify_check` (conditional: clarify vs discover/availability/action/answer). Compiled with LangGraph `StateGraph`; deterministic fallback when LangGraph/Grok unavailable. `GraphState` is explicit (text, intent, specialty, hospital/doctor/slot, appointment, clarification, response, route).

## Prompts
- Rephrase-only system prompt in `formulate_reply`: "Never diagnose/prescribe. Only rephrase given FACTS. Never invent doctors/slots/times. Symptoms only as 'you reported…'."
- Grok called via OpenAI-compatible client (`app/ai/grok_client.py`, `GROK_BASE_URL=https://api.x.ai/v1`). No key → rule-composed reply (demo fully works offline).

## MCP (`app/mcp/registry.py`)
17 tools: search_hospitals/doctors, check_availability, lookup_patient, get/create/reschedule/cancel_appointment, get/submit_questionnaire, send_notification, start_workflow, get_context, update_preferences, verify_external_appointment, synchronize_state, transfer_to_human. Each: auth check, tenant scope, audit row with latency + correlation; booking path idempotent + verified.

## Safety (`app/ai/safety.py`)
Blocklist for diagnose/prescribe/dosage patterns → refusal + care-team note + booking offer. Questionnaires are admin-approved only.

## Voice
`app/voice/providers.py` interface; frontend uses Web Speech API; `/api/v1/voice/*` returns client-mode hints unless `VOICE_API_KEY` + provider set. Turn-taking, barge-in (tap orb), async long-booking supported.

## Evaluation
Track: conversations, capability success/fail, escalation rate, latency (`ai_messages.latency_ms`, `capability_executions`), `ai_evaluations` table; admin AI Activity page surfaces traces.
