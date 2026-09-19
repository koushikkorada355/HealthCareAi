"""Clarification node: ask for what's missing instead of guessing.

Required slots per intent (filled from classification entities first, then
conversation context refs). One question at a time; explicit user picks
(recorded in context) always win over guesses.
"""
from __future__ import annotations

_REQUIRED = {
    "book": [("specialty", "Could you tell me which specialty or concern this is for — e.g. orthopedics (shoulder/joint), cardiology, dermatology, or general care? And which day suits you?")],
    "find_doctor": [("specialty", "Which specialty should I search — e.g. orthopedics, cardiology, dermatology, or general care?")],
    "find_hospital": [("city", "Which city should I search?")],
    "profile": [],
    "availability": [("doctor_id", "Which doctor should I check? Tell me a name and I'll look them up.")],
    "reschedule": [("appointment_id", "Which appointment should I move? Tell me the appointment number or its date and doctor.")],
    "cancel": [("appointment_id", "Which appointment should I cancel? Tell me the appointment number or its date and doctor.")],
    "questionnaire": [("appointment_id", "Which appointment is the questionnaire for?")],
    "hours": [("hospital_id", "Which hospital's hours do you need?")],
}


async def run(state: dict) -> dict:
    classification = state.get("classification") or {}
    intent = state.get("intent") or classification.get("intent", "unknown")
    entities = dict(classification.get("entities") or {})
    refs = dict(state.get("context_refs") or {})
    merged = {**refs, **{k: v for k, v in entities.items() if v not in (None, "")}}

    if intent in ("confirm", "decline", "greeting", "lookup", "notify", "escalate", "preferences"):
        return {"context_refs": merged,
                "trace": [*state.get("trace", []), f"clarify: {intent} needs nothing"]}

    for slot, question in _REQUIRED.get(intent, []):
        if merged.get(slot) in (None, ""):
            return {"context_refs": merged, "pending_clarification": question,
                    "trace": [*state.get("trace", []), f"clarify: missing {slot}"]}
    return {"context_refs": merged, "pending_clarification": "",
            "trace": [*state.get("trace", []), f"clarify: {intent} complete"]}


def route_after_clarification(state: dict) -> str:
    if state.get("reply"):
        return "response"
    if state.get("pending_clarification"):
        return "response"
    return "tool_router"
