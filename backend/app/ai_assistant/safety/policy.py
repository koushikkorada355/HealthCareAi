"""Deterministic safety policy — the authoritative hard control layer.

Runs BEFORE any MCP tool call and BEFORE any LLM output reaches the user.
The LLM safety reviewer (services/llm.py) is only a second signal: a
deterministic deny or escalate always wins; the LLM can never override it.

No user content is echoed in verdict details — only category labels.
"""
from __future__ import annotations

import re

# Clinical content: diagnosis, prescriptions, dosage, treatment, procedures,
# interpreting symptoms as conditions. Kept in sync with app/ai/safety.py
# (which remains the legacy path's enforcer).
CLINICAL_PATTERNS = [
    "diagnos", "prescrib", "dosage", "treatment plan", "medical procedure",
    "you have ", "you likely have", "you probably have",
    "take ibuprofen", "take aspirin", "take paracetamol", "take ",
    "what do i have", "what should i take", "am i sick", "do i have",
    "my diagnosis", "interpret my symptoms", "what disease",
    "should i take", "how much should i take",
]

# Urgent / high-risk language: never diagnose, never minimize — escalate with
# emergency direction + human handoff. Detection is routing-only; the layer
# makes no severity determination beyond matching this list.
URGENT_PATTERNS = [
    "severe chest pain", "chest pain", "can't breathe", "cannot breathe",
    "difficulty breathing", "trouble breathing", "heavy bleeding", "bleeding heavily",
    "unconscious", "fainted", "stroke", "heart attack", "suicide", "kill myself",
    "self-harm", "self harm", "overdose", "emergency", "call an ambulance",
    "severe bleeding", "choking", "seizure",
]

# Prompt-injection patterns: attempts to override system/safety/tool/tenant rules.
INJECTION_PATTERNS = [
    "ignore your", "ignore previous", "ignore all previous", "forget your instructions",
    "forget the previous", "you are now a doctor", "you are a doctor",
    "act as a doctor", "pretend to be a doctor", "as a doctor,",
    "disable safety", "turn off safety", "bypass", "override",
    "call the internal tool", "call the tool even", "run the tool",
    "system prompt", "reveal your instructions", "show your instructions",
    "jailbreak", "dan mode",
]

_HUMAN_PATTERNS = [
    "human", "real person", "someone real", "agent", "operator",
    "talk to a person", "speak to a person", "call me",
]


def _contains_any(text: str, patterns: list[str]) -> str | None:
    low = text.lower()
    for p in patterns:
        if p in low:
            return p
    return None


def check(text: str) -> dict:
    """Deterministic verdict for one user turn.

    Returns {"verdict": allow|deny|escalate, "reason_category": str}.
    Order matters: injection and urgent are checked before clinical so
    adversarial or high-risk turns can never slip into normal handling.
    """
    t = (text or "").strip()
    if not t:
        return {"verdict": "allow", "reason_category": ""}
    hit = _contains_any(t, INJECTION_PATTERNS)
    if hit:
        return {"verdict": "deny", "reason_category": "injection"}
    hit = _contains_any(t, URGENT_PATTERNS)
    if hit:
        return {"verdict": "escalate", "reason_category": "urgent"}
    hit = _contains_any(t, CLINICAL_PATTERNS)
    if hit:
        return {"verdict": "deny", "reason_category": "clinical"}
    return {"verdict": "allow", "reason_category": ""}


def wants_human(text: str) -> bool:
    """Explicit human-transfer request (handled before intent routing)."""
    low = (text or "").lower()
    return any(p in low for p in _HUMAN_PATTERNS) and any(
        w in low for w in ("want", "need", "get", "talk", "speak", "transfer", "escalate", "please", "can i", "could i")
    )


def clinical_refusal() -> str:
    return (
        "I can help with appointments and admin tasks, but I can't provide "
        "diagnosis or prescriptions. I've noted what you reported for the care team. "
        "Would you like me to find an available doctor?"
    )


def urgent_response() -> str:
    return (
        "What you're describing sounds urgent — please seek immediate care: call "
        "your local emergency number or go to the nearest emergency department "
        "right away. I've flagged this for a human on the care team, who will "
        "follow up here. If you can, stay with someone until help arrives."
    )


def injection_refusal() -> str:
    return (
        "I can't change how I work — my safety and authorization rules stay on. "
        "I'm happy to help with appointments, availability, questionnaires, or "
        "connecting you to a human."
    )
