"""Conversation context manager: history window + summarization.

Reads persisted AIMessage rows; never writes (the service layer persists).
Summaries preserve unresolved context (pending entity) over chatter.
"""
from __future__ import annotations

from .. import config


def load_history(db, conversation_id: int, limit: int | None = None) -> list[dict]:
    """Recent messages oldest-first as [{role, content}]. Fail-open → []."""
    try:
        from app import models

        rows = (
            db.query(models.AIMessage)
            .filter(models.AIMessage.conversation_id == conversation_id)
            .order_by(models.AIMessage.id.desc())
            .limit(limit or config.HISTORY_WINDOW)
            .all()
        )
        return [{"role": r.role, "content": r.content or ""} for r in reversed(rows)]
    except Exception:
        return []


def history_text(history: list[dict], max_chars: int = 1500) -> str:
    """Compact transcript tail for model context (bounded size)."""
    lines = [f"{m.get('role', '?')}: {(m.get('content') or '')[:300]}" for m in history]
    text = "\n".join(lines)
    return text[-max_chars:]


def needs_summary(count: int) -> bool:
    return count >= config.SUMMARY_THRESHOLD


def summarize_sync(history: list[dict], pending: dict | None = None) -> str:
    """Deterministic summary stub: topics + unresolved items, no LLM needed."""
    topics: list[str] = []
    for m in history:
        c = (m.get("content") or "").lower()
        for kw in ("book", "cancel", "reschedul", "doctor", "hospital", "slot", "questionnaire", "availab"):
            if kw in c and kw not in topics:
                topics.append(kw)
    base = f"Earlier discussion about: {', '.join(topics[:6]) or 'general help'}."
    if pending:
        base += f" Still unresolved: {pending}."
    return base


async def summarize(history: list[dict], pending: dict | None = None, llm=None) -> str:
    """LLM summary when available, deterministic stub otherwise."""
    if llm is not None and getattr(llm, "name", "") != "deterministic":
        try:
            out, used = await llm.rephrase(
                "Summarize this patient-assistant booking conversation in 2 sentences, "
                "keeping unresolved items (doctor, slot, time). Transcript:\n" + history_text(history, 3000)
            )
            if used and out:
                return out
        except Exception:
            pass
    return summarize_sync(history, pending)
