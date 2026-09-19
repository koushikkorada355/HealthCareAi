"""AI Assistant Layer — Phase 2: graph backbone, conversation, clarification.

Offline: deterministic LLM, no DB (empty _runtime db), in-memory states.
"""
import asyncio

from app.ai_assistant.graph.graph import build_graph, get_graph
from app.ai_assistant.services.llm import DeterministicLLM


def _run(text, extra=None):
    g = get_graph()
    state = {"messages": [{"role": "user", "content": text}],
             "_runtime": {"text": text, "llm": DeterministicLLM()},
             "trace": [], "data": {}}
    if extra:
        state.update(extra)
    return asyncio.run(g.ainvoke(state))


def test_graph_compiles_and_routes_book_to_tool():
    out = _run("I need to see a doctor for shoulder pain this week")
    assert out["intent"] == "book"
    assert out["safety"]["verdict"] == "allow"
    assert out.get("selected_tool", "") == "search_doctors"
    # No DB in this harness: the real adapter fails closed, never crashes.
    assert out["tool_status"] in ("selected", "skipped", "failed")
    if out["tool_status"] == "failed":
        assert "nothing was changed" in out["reply"].lower()
    assert out["reply"]
    assert any("conversation:" in t for t in out["trace"])
    assert any("classify:" in t for t in out["trace"])


def test_multi_turn_clarification_then_specialty():
    # Turn 1: vague booking -> clarification question, no tool.
    t1 = _run("I want to book an appointment.")
    assert t1.get("pending_clarification")
    assert t1.get("selected_tool", "") == ""
    assert "specialty" in t1["pending_clarification"].lower()
    # Turn 2: "Cardiology." answers the clarification (context retained via refs).
    t2 = _run("Cardiology.", {"context_refs": t1.get("context_refs", {})})
    assert t2.get("intent") == "find_doctor"
    assert t2.get("selected_tool", "") == "search_doctors"


def test_unrelated_goes_to_scope_not_tools():
    out = _run("tell me a joke about cats")
    assert out.get("selected_tool", "") == ""
    assert "healthcare" in out["reply"].lower() or "appointment" in out["reply"].lower()


def test_greeting_answers_without_tools():
    out = _run("hello")
    assert out["intent"] == "greeting"
    assert out.get("selected_tool", "") == ""
    assert "hello" in out["reply"].lower()


def test_cancel_needs_appointment_id():
    out = _run("cancel my appointment")
    assert out["intent"] == "cancel"
    assert out.get("pending_clarification", "")
    assert "appointment" in out.get("pending_clarification", "").lower()
    assert out.get("selected_tool", "") == ""


def test_find_hospital_needs_city():
    out = _run("find me a hospital")
    assert out["intent"] == "find_hospital"
    assert out.get("pending_clarification", "")
    assert out.get("selected_tool", "") == ""


def test_history_window_bounded():
    from app.ai_assistant.context import manager as m
    hist = [{"role": "user", "content": f"msg {i}"} for i in range(30)]
    assert len(m.history_text(hist)) <= 1500
    assert m.needs_summary(30) is True
    assert m.needs_summary(5) is False
    s = m.summarize_sync(hist, {"specialty": "orthopedics"})
    assert "orthopedics" in s or "book" in s


def test_safety_allow_reaches_scope():
    out = _run("what are your visiting hours")
    assert out["safety"]["verdict"] == "allow"
    assert out["trace"]


def test_confirm_without_pending_asks():
    out = _run("yes, book it")
    assert out["intent"] == "confirm"
    assert "nothing awaiting confirmation" in out.get("pending_clarification", "").lower() or out.get("selected_tool", "") == ""


def test_build_graph_structure():
    g = build_graph()
    assert g is not None
