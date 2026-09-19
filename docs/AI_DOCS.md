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

## AI Assistant Layer v2 (`app/ai_assistant/`, serves `POST /ai/chat` when `AI_ASSISTANT_V2=1`)
Dedicated LangGraph orchestration on top of the existing platform (Project2.pdf §§9–10, 20, 23–26).
No rebuilt backend, no duplicated models/services, no direct DB/EHR access from the LLM.

- **Flow:** conversation → context → classification → STRICT safety → scope → clarification → tool_router → tool_result → response (explicit conditional edges; `graph/graph.py` composes, all logic in `nodes/`).
- **State** (`graph/state.py`): conversation/user ids, bounded message window + summary, intent, classification, safety verdict, context refs (ids only), pending clarification/confirmation, selected tool + args, tool result + status, transfer, reply/trace/data. Application DB stays the source of truth.
- **Safety (architectural, not prompts):** deterministic policy (`safety/policy.py`: clinical/urgent/injection lists) beats any LLM second signal; urgent → emergency direction + human handoff; tool gating (reads free, writes only after explicit confirm with fresh idempotency key); response validator rejects invented slots/doctors/diagnoses pre-send. Denied turns never reach MCP (proven: zero `capability_executions` rows).
- **MCP:** `mcp/client.py` (timeout + normalized `{ok,code,data|error}`) + `mcp/adapter.py` (per-tool schemas validated pre-call) over the existing `registry.invoke` (22 tools). Confirm loop: write intents → echo-back summary → user yes → execute once (pending consumed; double-confirm is a no-op) → verified-result reply.
- **LLM:** provider-independent `services/llm.py` (`BaseLLM`; Grok structured-output impl; deterministic fallback reusing the v1 keyword interpreter with the `ent`-substring quirk fixed). Grok rephrases verified facts only.
- **Cutover:** `services/assistant.py run_turn()` owns the turn (conversation rows, slice persistence incl. pending, `graph_run_id`/`tool_call_id` observability, id-only logging); `POST /ai/chat` response shape unchanged plus `graph_run_id` + `safety`. Old path remains as exception fallback.
- **Channel-independent:** normalized text in, structured envelope out; `channel` passes through for web/voice/telephone. No voice changes in this build.
- **Tests:** `app/tests/test_ai_assistant_*.py` (60 cases: foundation, graph, 15-case safety battery, MCP confirm-loop, service/validator, gaps) + untouched legacy suites. Full suite green offline.
