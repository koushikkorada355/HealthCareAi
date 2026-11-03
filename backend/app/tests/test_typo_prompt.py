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
    assert "repaired_specialty" in RESPONSE_SYSTEM or "repaired_query" in RESPONSE_SYSTEM


def test_dates_global_no_wordlists():
    from datetime import datetime, timezone
    from app.ai_assistant.utils import dates as dates_mod
    import inspect

    src = inspect.getsource(dates_mod.normalize) + inspect.getsource(dates_mod.normalize_global)
    assert "monday" not in src.lower() and "january" not in src.lower()
    assert dates_mod.normalize("2026-09-25", now=datetime(2026, 9, 20, tzinfo=timezone.utc))["date_iso"] == "2026-09-25"
    out = dates_mod.normalize_global({"date_iso": "2026-09-25", "time_window": "morning"}, {})
    assert out["date_iso"] == "2026-09-25" and out["day_part"] == "morning"
