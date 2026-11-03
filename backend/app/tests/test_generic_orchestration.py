"""Generic orchestration proof: brand-new MCP tools work end-to-end with
ZERO changes to planner, router, resolver, executor, or response builder.

The dummy tools below are registered only in this test module. Every
assertion exercises shared generic code paths (catalog, plan validation,
arg resolution, execution, cards) without naming the tools anywhere else.
"""
import json

import pytest


@pytest.fixture()
def dummy_tools(monkeypatch):
    from app.ai_assistant.mcp import registry as reg

    async def _echo_ping(db, a, user=None, corr="", idem="", conversation_id=None):
        return {"pong": a.get("message", ""), "echo_id": 7}

    async def _sum_numbers(db, a, user=None, corr="", idem="", conversation_id=None):
        return {"total": int(a["x"]) + int(a["y"])}

    monkeypatch.setitem(reg._IMPL, "echo_ping", _echo_ping)
    monkeypatch.setitem(reg._IMPL, "sum_numbers", _sum_numbers)
    monkeypatch.setitem(reg.TOOL_SCHEMAS, "echo_ping",
                        {"required": ["message"], "int_args": []})
    monkeypatch.setitem(reg.TOOL_SCHEMAS, "sum_numbers",
                        {"required": ["x", "y"], "int_args": ["x", "y"]})
    caps = list(reg.CAPABILITIES)
    caps.append({"name": "echo_ping", "description": "Echo a message (message)",
                 "idempotent": True})
    caps.append({"name": "sum_numbers", "description": "Add two numbers (x, y)",
                 "idempotent": True})
    monkeypatch.setattr(reg, "CAPABILITIES", caps)
    return reg


def test_catalog_lists_new_tools_without_code_changes(dummy_tools):
    from app.ai_assistant import orchestration as orch

    names, catalog = orch.build_catalog()
    assert "echo_ping" in names and "sum_numbers" in names
    assert "echo_ping" in catalog and "sum_numbers" in catalog


def test_plan_validation_accepts_new_tools(dummy_tools):
    from app.ai_assistant import orchestration as orch

    steps, err = orch.validate_plan([
        {"id": "s1", "tool": "echo_ping", "args": {"message": "hi"}},
        {"id": "s2", "tool": "sum_numbers", "args": {"x": "$step_s1.echo_id", "y": 3},
         "depends_on": ["s1"]},
    ])
    assert err == {} and [s["id"] for s in steps] == ["s1", "s2"]
    bad, err2 = orch.validate_plan([{"tool": "nope_tool", "args": {}}])
    assert bad == [] and err2["wanted"] == "nope_tool"


def test_resolve_args_uses_schema_dynamically(dummy_tools):
    from app.ai_assistant import orchestration as orch

    out, err = orch.resolve_args("sum_numbers", {"x": "2", "y": "3"},
                                 {"messages": [], "context_refs": {}}, {})
    assert err == "" and out == {"x": 2, "y": 3}
    out2, err2 = orch.resolve_args("sum_numbers", {"x": 1},
                                   {"messages": [], "context_refs": {}}, {})
    assert "Missing required arguments: y" in err2


def test_ref_wiring_is_generic(dummy_tools):
    from app.ai_assistant import orchestration as orch

    state = {"tool_result": {"data": {"echo_id": 7}},
             "step_outputs": [{"step_id": "s1", "tool": "echo_ping",
                               "data": {"echo_id": 7}}]}
    out, err = orch.resolve_args(
        "sum_numbers", {"x": "$prev.echo_id", "y": "$step_s1.echo_id"},
        state, {})
    assert err == "" and out == {"x": 7, "y": 7}


async def _run_router_with_plan(monkeypatch, plan):
    from app.ai_assistant.nodes import tool_router as tr
    from app.ai_assistant.services import llm as llm_mod

    async def _fake(messages, system=""):
        class R:
            content = json.dumps({"plan": plan})
        return R()

    monkeypatch.setattr(llm_mod, "generate", _fake)
    state = {"messages": [{"role": "user", "content": "ping then add"}],
             "classification": {}, "context_refs": {}, "history_text": "",
             "trace": [], "completed_step_ids": []}
    return await tr.run(state)


def test_router_plans_and_resolves_new_tool(monkeypatch, dummy_tools):
    import asyncio as _a

    out = _a.run(_run_router_with_plan(
        monkeypatch, [{"id": "s1", "tool": "echo_ping", "args": {"message": "hi"}}]))
    assert out["selected_tool"] == "echo_ping"
    assert out["tool_args"] == {"message": "hi"}


def test_router_chains_new_tools_via_refs(monkeypatch, dummy_tools):
    import asyncio as _a

    out = _a.run(_run_router_with_plan(monkeypatch, [
        {"id": "s1", "tool": "echo_ping", "args": {"message": "hi"}},
        {"id": "s2", "tool": "sum_numbers",
         "args": {"x": "$step_s1.echo_id", "y": 5}, "depends_on": ["s1"]},
    ]))
    assert out["selected_tool"] == "echo_ping"
    assert len(out["plan_steps"]) == 1 and out["plan_steps"][0]["id"] == "s2"


def test_executor_runs_new_tool(monkeypatch, dummy_tools):
    import asyncio as _a
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import models
    from app.ai_assistant.nodes import tool_result
    from app.db.base import Base

    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    db = sessionmaker(bind=e)()
    db.add(models.User(email="gen_t@example.org", role="patient", password_hash="x"))
    db.commit()
    conv = models.AIConversation(user_id=1, channel="web", correlation_id="gen1")
    db.add(conv)
    db.commit()

    class _U:
        role, id, patient_id, hospital_id = "patient", 1, 1, None

    async def _go():
        return await tool_result.run({
            "selected_tool": "echo_ping", "tool_args": {"message": "hi"},
            "pending_confirmation": {"idempotency_key": "k1"},
            "_runtime": {"db": db, "user": _U(), "corr": "c1"},
            "conversation_id": conv.id, "hop_count": 0, "trace": [],
            "plan_steps": [], "step_outputs": []})

    out = _a.run(_go())
    assert out["tool_status"] == "ok"
    assert out["tool_result"]["data"] == {"pong": "hi", "echo_id": 7}


def test_card_renders_new_tool_result(dummy_tools):
    from app.ai_assistant import orchestration as orch

    card = orch.build_card("echo_ping", {"pings": [{"id": 1, "message": "hi"}]})
    assert card["card"] == "pings" and card["items"][0]["message"] == "hi"
