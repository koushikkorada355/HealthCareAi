"""MCP adapter: schema validation + routing. No business logic here."""
from __future__ import annotations

REQUIRED_ARGS: dict[str, list[str]] = {
    "search_hospitals": [], "search_doctors": [],
    "get_doctor_details": [], "get_hospital_details": [],
    "check_availability": ["doctor_id"], "lookup_patient": [],
    "get_appointment": ["appointment_id"],
    "create_appointment": ["hospital_id", "doctor_id", "patient_id", "starts_at", "ends_at"],
    "reschedule_appointment": ["appointment_id", "new_starts_at", "new_ends_at"],
    "cancel_appointment": ["appointment_id"],
    "get_questionnaire": ["questionnaire_id"], "submit_questionnaire": ["response_id"],
    "send_notification": [], "start_workflow": ["event"],
    "get_context": ["conversation_id"], "update_preferences": [],
    "verify_external_appointment": [], "synchronize_state": ["appointment_id"],
    "transfer_to_human": [], "get_reviews": [],
    "list_my_appointments": [], "list_my_questionnaires": [], "get_notifications": [],
}

INT_ARGS = {
    "check_availability": ["doctor_id"],
    "get_appointment": ["appointment_id"],
    "create_appointment": ["hospital_id", "doctor_id", "patient_id"],
    "reschedule_appointment": ["appointment_id"],
    "cancel_appointment": ["appointment_id"],
    "get_questionnaire": ["questionnaire_id"],
    "submit_questionnaire": ["response_id"],
    "synchronize_state": ["appointment_id"],
    "get_context": ["conversation_id"],
}


def known_tools() -> list[str]:
    from app.ai_assistant.mcp import registry as reg

    return [t["name"] for t in reg.CAPABILITIES]


def validate(name: str, args: dict | None) -> tuple[dict, str]:
    from app.ai_assistant.mcp import registry as reg

    if name not in reg._IMPL:
        return {}, f"Unknown capability {name}."
    args = dict(args or {})
    missing = [k for k in REQUIRED_ARGS.get(name, []) if args.get(k) in (None, "")]
    if missing:
        return {}, f"Missing required arguments: {', '.join(missing)}."
    coerced = dict(args)
    for k in INT_ARGS.get(name, []):
        if coerced.get(k) in (None, ""):
            continue
        try:
            coerced[k] = int(coerced[k])
        except (TypeError, ValueError):
            return {}, f"Argument {k} must be an integer."
    return coerced, ""


async def call(db, name: str, args: dict | None, *, user, conversation_id=None,
               idempotency_key: str = "", corr: str = "",
               tool_call_id: str = "", timeout_s: float | None = None) -> dict:
    from app.ai_assistant.mcp import client as mcp_client

    coerced, error = validate(name, args)
    if error:
        return {"ok": False, "code": "invalid", "error": error,
                "latency_ms": 0, "tool_call_id": tool_call_id}
    out = await mcp_client.invoke(
        db, name, coerced, user=user, conversation_id=conversation_id,
        idempotency_key=idempotency_key, corr=corr or "", timeout_s=timeout_s)
    out["tool_call_id"] = tool_call_id or mcp_client.new_tool_call_id()
    return out
