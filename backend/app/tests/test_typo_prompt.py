"""Typo tolerance is prompt-based (non-deterministic) by design.

No typo tables, no regex dictionaries: Mercury maps misspellings via
repaired_specialty/repaired_query in classify output, and the router/response
prompts prefer those values + ask 'did you mean?' on empty results.
"""
import json
import pytest


class _Res:
    def __init__(self, content):
        self.content = content
        self.powered_by = "mercury-2.5-test"
        self.latency_ms = 1


async def _fake_generate(messages, system=""):
    return _Res(json.dumps({
        "intent": "book", "category": "admin", "specialty": "",
        "urgency": "routine", "dates": "this week", "safety_flag": "",
        "repaired_specialty": "Orthopedics",
        "repaired_query": "I need a shoulder doctor this week",
    }))


async def test_classify_parses_repaired_fields(monkeypatch):
    from app.ai_assistant.services import llm as llm_mod

    monkeypatch.setattr(llm_mod, "generate", _fake_generate)
    out = await llm_mod.classify("I need a sholder doctor this week")
    assert out["intent"] == "book"
    assert out["repaired_specialty"] == "Orthopedics"
    assert "shoulder" in out["repaired_query"]


async def test_classify_missing_repair_keys_default_empty(monkeypatch):
    from app.ai_assistant.services import llm as llm_mod

    async def _old(messages, system=""):
        return _Res(json.dumps({"intent": "greeting", "category": "admin"}))

    monkeypatch.setattr(llm_mod, "generate", _old)
    out = await llm_mod.classify("hi")
    assert out["repaired_specialty"] == "" and out["repaired_query"] == ""


def test_prompts_carry_spelling_guidance():
    from app.ai_assistant.prompts.system import ROUTER_SYSTEM, RESPONSE_SYSTEM

    assert "repaired_specialty" in ROUTER_SYSTEM
    assert "repaired_query" in ROUTER_SYSTEM
    assert "Did you mean" in RESPONSE_SYSTEM
    # Empty results from a possible misspelling must not jump to escalation.
    assert "never log a tracked request for what may be a spelling mistake" in RESPONSE_SYSTEM


def test_dates_normalize_still_deterministic():
    from datetime import datetime, timezone
    from app.ai_assistant.utils import dates as dates_mod
    import inspect

    # No typo-table imports: repair stays in the LLM layer.
    assert "typo" not in inspect.getsource(dates_mod.normalize)
    out = dates_mod.normalize("Friday morning", now=datetime(2026, 9, 20, tzinfo=timezone.utc))
    assert out["date_iso"] == "2026-09-25" and out["day_part"] == "morning"
