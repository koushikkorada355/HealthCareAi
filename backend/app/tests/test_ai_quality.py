"""Quality tests: date normalization, backfill, reply guardrails, new tool wiring."""
from datetime import datetime, timezone

from app.ai_assistant.utils.dates import normalize


def test_normalize_relative_days():
    now = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)
    assert normalize("book for tomorrow afternoon", now)["date_iso"] == "2026-09-21"
    assert normalize("book for tomorrow afternoon", now)["day_part"] == "afternoon"
    assert normalize("today morning", now)["date_iso"] == "2026-09-20"
    assert normalize("20 september", now)["date_iso"] == "2026-09-20"
    assert normalize("monday september 21st evening", now)["day_part"] == "evening"
    assert normalize("this week", now)["days"] == 7
    assert normalize("hello there", now) == {}


def test_backfill_availability_args():
    from app.ai_assistant.nodes import tool_router as tr

    state = {"messages": [], "context_refs": {"transactional": {
        "doctor_id": 3, "doctor_name": "Dr. Sara Khan",
        "hospital_id": 1, "time_window": "afternoon"}}}
    norm = {"date_iso": "2026-09-20", "days": 1}
    out = tr._backfill("check_availability", {}, state, norm, [], state["context_refs"]["transactional"])
    assert out["doctor_id"] == 3
    assert out["date"] == "2026-09-20"
    assert out["day_part"] == "afternoon"


def test_backfill_single_candidate():
    from app.ai_assistant.nodes import tool_router as tr

    cands = [{"doctor_id": 1, "doctor_name": "Dr. Maya Rao", "hospital_id": 1, "hospital_name": "City"}]
    out = tr._backfill("check_availability", {}, {"messages": []}, {"date_iso": "2026-09-21"}, cands, {})
    assert out["doctor_id"] == 1
    assert out["date"] == "2026-09-21"


def test_reply_violations():
    from app.ai_assistant.nodes.response import violations

    assert violations("We are working to secure your slot.", True) != []
    assert violations("Please contact CityCare directly.", True) != []
    assert violations("Log into your patient portal.", True) != []
    assert violations("You reported pain. Here are slots.", True) != []
    assert violations("I don't have access to questionnaires.", False) != []
    assert violations("Here are 3 open slots tomorrow afternoon.", True) == []
    assert violations("I can't diagnose that — let me connect you.", True) == []
    # False booking confirmations.
    assert violations("Done — appointment #42 booked and verified.", True) != []
    assert violations("Done — appointment #42 booked and verified.", True, True) == []
    assert violations("Your visit is scheduled for Friday.", True) != []
    # Text/card duplication.
    assert violations("Dr. Sara Khan at 09:00 on 2026-09-21.", True, dup_hits=3) != []
    assert violations("Here are your options:", True, dup_hits=1) == []
    # Speculation only flagged when no data backs it.
    assert violations("You could also explore other providers.", True, speculative=True) != []
    assert violations("You could also explore other providers.", True, speculative=False) == []
    # No live agent may ever be promised.
    assert violations("I can connect you with a human assistant to help.", True) != []
    assert violations("A team member will follow up shortly.", True) != []
    assert violations("Logged as tracked request #12 for the care team.", True) == []


def test_new_tool_registered():
    from app.ai_assistant.mcp import adapter

    assert "list_my_questionnaires" in adapter.known_tools()
    assert len(adapter.known_tools()) == 23
    coerced, err = adapter.validate("list_my_questionnaires", {})
    assert err == "" and coerced == {}


def test_global_search_exclusion():
    import json as _j
    from app import models
    from app.db.base import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    db = sessionmaker(bind=e)()
    h1 = models.Hospital(name="CityCare General Hospital", slug="cc", status="approved")
    h2 = models.Hospital(name="Riverside Specialty Clinic", slug="rs", status="approved")
    db.add_all([h1, h2]); db.commit()
    import asyncio as _a

    class _U:
        role = "patient"
        id = 1
        patient_id = 1
        hospital_id = None

    async def _run():
        from app.ai_assistant.mcp import registry as reg
        all_r = await reg._search_doctors(db, {}, user=_U())
        assert {d["hospital_name"] for d in all_r["doctors"]} == set()
        db.add_all([
            models.Doctor(hospital_id=h1.id, name="Dr A", status="active"),
            models.Doctor(hospital_id=h2.id, name="Dr B", status="active")])
        db.commit()
        all_r = await reg._search_doctors(db, {}, user=_U())
        assert {d["hospital_name"] for d in all_r["doctors"]} == {"CityCare General Hospital", "Riverside Specialty Clinic"}
        excl = await reg._search_doctors(db, {"exclude_hospital": "CityCare"}, user=_U())
        assert {d["hospital_name"] for d in excl["doctors"]} == {"Riverside Specialty Clinic"}
        named = await reg._search_doctors(db, {"hospital": "Riverside"}, user=_U())
        assert {d["hospital_name"] for d in named["doctors"]} == {"Riverside Specialty Clinic"}

    _a.run(_run())


def test_router_catalog_has_required_args():
    from app.ai_assistant.mcp import adapter
    from app.ai_assistant.mcp import registry as reg
    from app.ai_assistant.prompts.system import ROUTER_SYSTEM

    lines = []
    for t in reg.CAPABILITIES:
        req = ", ".join(adapter.REQUIRED_ARGS.get(t["name"], [])) or "none"
        lines.append(f"- {t['name']}: {t['description']} [required: {req}]")
    prompt = ROUTER_SYSTEM.replace("__CATALOG__", "\n".join(lines))
    assert "check_availability" in prompt and "doctor_id" in prompt


async def test_router_consumes_stored_plan_without_llm(monkeypatch):
    from app.ai_assistant.nodes import tool_router as tr
    from app.ai_assistant.services import llm as llm_mod

    async def _boom(*a, **k):
        raise AssertionError("LLM must not be called when a plan is stored")

    monkeypatch.setattr(llm_mod, "generate", _boom)
    state = {"messages": [{"role": "user", "content": "cardiologists in CityCare"}],
             "classification": {}, "context_refs": {}, "history_text": "",
             "plan_steps": [{"tool": "search_doctors", "args": {"specialty": "Cardiology"}}],
             "trace": []}
    out = await tr.run(state)
    assert out["selected_tool"] == "search_doctors"
    assert out["tool_args"]["specialty"] == "Cardiology"
    assert out["plan_steps"] == []
    assert "router:plan:search_doctors" in out["trace"]


async def test_router_unavailable_path(monkeypatch):
    import json as _j
    from app.ai_assistant.nodes import tool_router as tr
    from app.ai_assistant.services import llm as llm_mod

    async def _fake(messages, system=""):
        class R:
            content = _j.dumps({"plan": [], "unavailable": "billing statements",
                                "alternatives": ["list_my_appointments"]})
        return R()

    monkeypatch.setattr(llm_mod, "generate", _fake)
    state = {"messages": [{"role": "user", "content": "show my bills"}],
             "classification": {}, "context_refs": {}, "history_text": "",
             "trace": []}
    out = await tr.run(state)
    assert out["selected_tool"] == ""
    assert out["missing_tool"]["wanted"] == "billing statements"
    assert out["missing_tool"]["alternatives"] == ["list_my_appointments"]
    assert "router:unavailable" in out["trace"]


def test_plan_wiring_prev():
    from app.ai_assistant.nodes.tool_router import _wire

    state = {"tool_result": {"data": {"doctor_id": 3, "appointment_id": 9}}}
    assert _wire({"doctor_id": "$prev.doctor_id", "x": 1}, state) == {"doctor_id": 3, "x": 1}
    assert _wire({"a": "$prev.missing"}, state)["a"] == "$prev.missing"


def test_result_plan_chaining():
    from app.ai_assistant.nodes import tool_result

    assert tool_result.route_after_result(
        {"tool_status": "ok", "hop_count": 1, "plan_steps": [{"tool": "x"}]}) == "tool_router"
    assert tool_result.route_after_result(
        {"tool_status": "ok", "hop_count": 1, "plan_steps": []}) == "response"
    assert tool_result.route_after_result(
        {"tool_status": "failed", "hop_count": 1, "plan_steps": [{"tool": "x"}]}) == "response"


def test_card_actions_global():
    from app.ai_assistant.nodes.response import _card

    docs = _card("search_doctors", {"doctors": [
        {"id": 3, "doctor_name": "Dr. Sara Khan", "hospital_name": "CityCare"}]})
    assert docs["card"] == "doctors"
    assert docs["items"][0]["actions"][0]["text"] == \
        "Check availability for Dr. Sara Khan at CityCare"
    slots = _card("check_availability", {"doctor_id": 3, "slots": [
        {"starts_at": "2026-09-21T09:00:00+00:00", "ends_at": "2026-09-21T09:30:00+00:00"}]},
        "Dr. Sara Khan")
    assert slots["card"] == "slots"
    assert "Dr. Sara Khan" in slots["items"][0]["actions"][0]["text"]
    appts = _card("list_my_appointments", {"appointments": [{"id": 11}]})
    labels = [a["label"] for a in appts["items"][0]["actions"]]
    assert labels == ["Details"]
    assert _card("get_reviews", {"reviews": [{"rating": 5}]})["items"]


def test_input_options_global():
    from app.ai_assistant.nodes.response import _options

    esc = _options({"safety": {"verdict": "escalate"},
                    "pending_clarification_fields": []})
    assert [o["label"] for o in esc] == ["Yes, log it", "Not now"]
    assert esc[0]["text"] == "Yes, log this for the care team"
    date_o = _options({"safety": {"verdict": "allow"},
                       "pending_clarification_fields": ["date_hint"],
                       "context_refs": {"transactional": {}}})
    assert [o["label"] for o in date_o] == ["Today", "Tomorrow", "This week"]
    doc_o = _options(
        {"safety": {"verdict": "allow"},
         "pending_clarification_fields": ["specialty_or_doctor"],
         "step_outputs": [{"tool": "search_doctors", "data": {"doctors": [
             {"doctor_name": "Dr. A", "hospital_name": "H1"},
             {"doctor_name": "Dr. A", "hospital_name": "H1"}]}}]})
    assert len(doc_o) == 1 and doc_o[0]["text"] == "Dr. A at H1"
    assert _options({"safety": {"verdict": "allow"},
                     "pending_clarification_fields": []}) == []


def test_resolve_slot_matching():
    from app.ai_assistant.nodes.tool_router import _resolve_slot

    slots = [
        {"doctor_id": 3, "calendar_id": 7, "starts_at": "2026-09-21T09:00:00+00:00",
         "ends_at": "2026-09-21T09:30:00+00:00"},
        {"doctor_id": 3, "calendar_id": 7, "starts_at": "2026-09-21T15:00:00+00:00",
         "ends_at": "2026-09-21T15:30:00+00:00"},
        {"doctor_id": 5, "calendar_id": 9, "starts_at": "2026-09-21T09:00:00+00:00",
         "ends_at": "2026-09-21T09:30:00+00:00"},
    ]
    state = {"step_outputs": [{"tool": "check_availability",
                               "data": {"doctor_id": 3, "slots": slots}}]}
    hit = _resolve_slot(state, {"date_iso": "2026-09-21", "day_part": "afternoon"}, 3)
    assert hit["starts_at"] == "2026-09-21T15:00:00+00:00"
    assert _resolve_slot(state, {"date_iso": "2026-09-22"}, 3) == {}
    assert _resolve_slot(state, {}, 0)["doctor_id"] == 3


def test_dup_counter():
    from app.ai_assistant.nodes.response import _dup_count

    card = {"card": "slots", "items": [
        {"doctor_name": "Dr. Sara Khan", "starts_at": "2026-09-21T09:00:00+00:00",
         "ends_at": "2026-09-21T09:30:00+00:00"}]}
    assert _dup_count("Dr. Sara Khan at 9:00 AM on 2026-09-21.", card) >= 3
    assert _dup_count("Here are your options below.", card) == 0
    assert _dup_count("Anything", {}) == 0
