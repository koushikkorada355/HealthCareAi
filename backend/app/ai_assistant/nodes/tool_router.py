"""Tool router node: intent → validated tool call or pending confirmation.

Reads never execute from vague turns (clarification already ensured the
required refs). Writes NEVER execute here: reschedule/cancel (and later
create/submit) land in pending_confirmation with a human echo-back plus a
fresh idempotency key, executed only after explicit user confirmation.

Unknown tools are unreachable: INTENT maps cover the allowlist, and the
adapter re-validates before any call.
"""
from __future__ import annotations

import uuid

# Intent → tool mapping. Reads end in tool selection; writes end in a
# pending_confirmation that Phase 4 executes after explicit user confirm.
INTENT_TO_TOOL = {
    "find_doctor": "search_doctors",
    "find_hospital": "search_hospitals",
    "profile": "profile_lookup",
    "availability": "check_availability",
    "lookup": "lookup_patient",
    "questionnaire": "get_questionnaire",
    "hours": "get_hospital_details",
    "book": "search_doctors",
    "reschedule": "reschedule_appointment",
    "cancel": "cancel_appointment",
}

WRITE_TOOLS = {
    "create_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "submit_questionnaire",
    "send_notification",
    "start_workflow",
    "synchronize_state",
    "update_preferences",
}

# Some intents name a write operation outright; those never execute from
# intent alone — they land in pending_confirmation for the Phase 4 confirm
# loop. `book` stays discovery-first (search_doctors); the create tool is
# proposed only once doctor+slot are known and the user confirms.
INTENT_WRITE_TOOL = {
    "reschedule": "reschedule_appointment",
    "cancel": "cancel_appointment",
}


async def run(state: dict) -> dict:
    classification = state.get("classification") or {}
    intent = state.get("intent") or classification.get("intent", "unknown")
    entities = dict(classification.get("entities") or {})
    refs = dict(state.get("context_refs") or {})
    trace = list(state.get("trace", []))
    merged = {**refs, **{k: v for k, v in entities.items() if v not in (None, "")}}

    if intent == "decline":
        return {"selected_tool": "", "tool_args": {}, "tool_status": "skipped",
                "pending_confirmation": {},
                "reply": ("Understood — I won't change anything. "
                          "What would you like to do instead?"),
                "trace": [*trace, "router: declined, pending cleared"]}

    if intent == "confirm":
        pending = state.get("pending_confirmation") or {}
        if pending.get("tool") in WRITE_TOOLS:
            args = dict(pending.get("args") or {})
            for k, v in merged.items():
                if v not in (None, ""):
                    args[k] = v
            return {"selected_tool": pending["tool"], "tool_args": args,
                    "tool_status": "confirmed",
                    "trace": [*trace, f"router: confirmed {pending['tool']}"]}
        return {"selected_tool": "", "tool_args": {}, "tool_status": "skipped",
                "pending_clarification": "There's nothing awaiting confirmation — what would you like to do?",
                "trace": [*trace, "router: confirm with empty pending"]}

    tool = INTENT_TO_TOOL.get(intent, "")
    if not tool:
        return {"selected_tool": "", "tool_args": {}, "tool_status": "skipped",
                "trace": [*trace, f"router: no tool for {intent}"]}
    args = {k: merged[k] for k in ("specialty", "city", "doctor_id", "hospital_id", "appointment_id",
                                   "date_pref", "slot_iso", "q", "name") if merged.get(k) not in (None, "")}
    if intent in INTENT_WRITE_TOOL:
        from ..mcp.adapter import REQUIRED_ARGS

        tool = INTENT_WRITE_TOOL[intent]
        need = [k for k in REQUIRED_ARGS.get(tool, []) if args.get(k) in (None, "")]
        if need:
            need_q = {"appointment_id": "Which appointment? Tell me the appointment number or its date and doctor.",
                      "new_starts_at": "Which new date and time should I move it to?",
                      "new_ends_at": "And what time should it end?"}
            return {"selected_tool": "", "tool_args": {},
                    "pending_clarification": need_q.get(need[0], f"Please provide: {', '.join(need)}."),
                    "tool_status": "skipped",
                    "trace": [*trace, f"router: {tool} missing {need}"]}
        summary = _summarize_write(tool, args)
        return {"selected_tool": "", "tool_args": {},
                "pending_confirmation": {"tool": tool, "args": args,
                                         "idempotency_key": uuid.uuid4().hex,
                                         "summary": summary},
                "tool_status": "skipped",
                "trace": [*trace, f"router: {tool} pending confirmation"]}
    return {"selected_tool": tool, "tool_args": args, "tool_status": "selected",
            "trace": [*trace, f"router: {tool} {sorted(args)}"]}


def _summarize_write(tool: str, args: dict) -> str:
    if tool == "cancel_appointment":
        return f"Cancel appointment #{args.get('appointment_id')}."
    if tool == "reschedule_appointment":
        return (f"Move appointment #{args.get('appointment_id')} to "
                f"{args.get('new_starts_at')} – {args.get('new_ends_at')}.")
    return f"Run {tool} with the confirmed details."


def route_after_router(state: dict) -> str:
    if state.get("tool_status") == "confirmed":
        return "result"
    if state.get("selected_tool"):
        return "result"
    return "response"
