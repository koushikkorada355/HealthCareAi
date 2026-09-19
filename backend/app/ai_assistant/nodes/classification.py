"""Classification node: structured understanding via LLM + fallback."""
from __future__ import annotations


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    llm = rt.get("llm")
    messages = state.get("messages", []) or []
    text = messages[-1].get("content", "") if messages else rt.get("text", "")
    history = state.get("history_text", "")

    if llm is None:
        from ..services.llm import get_llm

        llm = get_llm()
    cls = await llm.classify(text, history)
    return {
        "intent": cls.intent,
        "classification": {
            "category": cls.category,
            "intent": cls.intent,
            "entities": dict(cls.entities or {}),
            "confidence": cls.confidence,
            "needs_action_write": cls.needs_action_write,
        },
        "trace": [*state.get("trace", []),
                  f"classify: {cls.category}/{cls.intent} ({llm.name})"],
    }
