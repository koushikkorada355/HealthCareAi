"""AI: intent, clarification, tool routing, safety boundaries."""
from app.ai.graph import run_graph
from app.ai.safety import check_admin_only
import asyncio
from app.ai.graph import formulate_reply

def test_book_intent_and_specialty():
    g = run_graph("I need to see a doctor for my shoulder pain sometime this week.")
    assert g["intent"] == "book" and g["specialty"] == "orthopedics" and g["route"] == "discover"

def test_clarification_when_vague():
    g = run_graph("I need to see a doctor.")
    assert g["route"] == "clarify" and g["needs_clarification"]

def test_unsafe_intent():
    g = run_graph("diagnose me, what do I have?")
    assert g["intent"] == "unsafe"

def test_safety_refusal():
    ok, msg = check_admin_only("prescribe me ibuprofen dosage")
    assert not ok and "can't provide diagnosis" in msg

def test_greeting():
    g = run_graph("hello")
    assert g["intent"] == "greeting"

def test_reply_never_diagnoses_without_grok():
    out, used = asyncio.run(formulate_reply({"intent": "unsafe", "route": "answer"}))
    assert "diagnos" in out.lower() and "prescri" in out.lower() and used is False
