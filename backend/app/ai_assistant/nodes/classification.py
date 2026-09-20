"""classification node: LLM intent (fail-closed — raises when LLM down)."""
from __future__ import annotations


async def run(state: dict) -> dict:
    from app.ai_assistant.services import llm as llm_mod

    text = ""
    for m in reversed(state.get("messages", [])):
        if m.get("role") == "user":
            text = m.get("content", "")
            break
    prior_turns = " | ".join(
        f"{m.get('role')}: {(m.get('content') or '')[:300]}"
        for m in (state.get("messages", []) or [])[-5:-1])
    history = f"{state.get('conversation_summary', '')}\n{prior_turns}"[:2000]
    data = await llm_mod.classify(text, history)
    trace = [*state.get("trace", []),
             f"classify:{data.get('intent')}/{data.get('category')}"]
    return {"intent": data.get("intent", "ambiguous"), "classification": data,
            "powered_by": data.get("powered_by", ""), "trace": trace}
