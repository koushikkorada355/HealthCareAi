"""Scope node: healthcare-administrative boundary.

Unrelated or unsupported turns end here with a brief redirect — no tools,
no application operations, no hallucinated answers.
"""
from __future__ import annotations


async def run(state: dict) -> dict:
    classification = state.get("classification") or {}
    category = classification.get("category", "ambiguous")
    if category in ("unrelated", "unsupported"):
        return {
            "pending_clarification": "",
            "reply": ("I'm designed for healthcare appointments and admin help — "
                      "finding hospitals and doctors, checking real availability, "
                      "booking, rescheduling, questionnaires, and reminders. "
                      "What would you like to do there?"),
            "trace": [*state.get("trace", []), f"scope: {category}"],
        }
    return {"trace": [*state.get("trace", []), f"scope: {category}"]}  # in-scope


def route_after_scope(state: dict) -> str:
    if state.get("reply"):
        return "response"
    return "clarification"
