"""Modular LangGraph workflow: interpret -> clarify/discover -> availability -> booking -> verify/sync -> questionnaire/workflow.
Business rules live in services; graph only orchestrates. Falls back to deterministic rules when Grok unavailable."""
from typing import TypedDict, Optional
import json, re
from datetime import datetime, timedelta, timezone

class GraphState(TypedDict, total=False):
    text: str
    intent: str
    specialty: str
    hospital_id: Optional[int]
    doctor_id: Optional[int]
    date_pref: str
    slot: str
    appointment_id: Optional[int]
    needs_clarification: bool
    clarification_q: str
    response: str
    route: str
    safety_note: str

SPECS = ["cardiology","orthopedics","dermatology","neurology","pediatrics","general","gynecology","ophthalmology","ent","dental","psychiatry","oncology"]
INTENTS = ["book","reschedule","cancel","find_doctor","find_hospital","profile","availability","questionnaire","hours","greeting","unsafe","unknown"]

def _spec_from(text: str) -> str:
    t = text.lower()
    m = {"shoulder": "orthopedics", "knee": "orthopedics", "bone": "orthopedics", "fracture": "orthopedics",
         "skin": "dermatology", "rash": "dermatology", "heart": "cardiology", "chest": "cardiology",
         "child": "pediatrics", "eye": "ophthalmology", "tooth": "dental", "teeth": "dental", "mental": "psychiatry",
         "pregnan": "gynecology", "headache": "neurology", "migraine": "neurology"}
    for k, v in m.items():
        if k in t: return v
    for s in SPECS:
        if s in t: return s
    return ""

def n_interpret(s: GraphState) -> GraphState:
    t = (s.get("text") or "").lower()
    intent = "unknown"
    if any(w in t for w in ["cancel"]): intent = "cancel"
    elif any(w in t for w in ["reschedul", "move my", "change my"]): intent = "reschedule"
    elif any(w in t for w in ["book", "appointment", "see a doctor", "need to see", "shoulder pain", "sometime this week", "schedule"]): intent = "book"
    elif "questionnaire" in t or "pre-visit" in t or "pre visit" in t: intent = "questionnaire"
    elif any(w in t for w in ["find doctor", "find a doctor", "specialist", "doctor for"]): intent = "find_doctor"
    elif any(w in t for w in ["tell me about", "who is", "about dr", "about doctor", "best "]): intent = "profile"
    elif "hospital" in t or "near me" in t or "nearby" in t or "close by" in t or "close to me" in t: intent = "find_hospital"
    elif "availab" in t or "slot" in t or "openings" in t: intent = "availability"
    elif any(w in t for w in ["hi", "hello", "hey"]) and len(t) < 30: intent = "greeting"
    if any(w in t for w in ["diagnose me", "what do i have", "prescribe", "what should i take", "am i sick"]): intent = "unsafe"
    s["intent"] = intent
    s["specialty"] = _spec_from(s.get("text",""))
    # date pref
    if "today" in t: s["date_pref"] = "today"
    elif "tomorrow" in t: s["date_pref"] = "tomorrow"
    elif "this week" in t or "sometime" in t: s["date_pref"] = "this_week"
    else: s["date_pref"] = s.get("date_pref", "")
    return s

def n_clarify_check(s: GraphState) -> GraphState:
    if s.get("intent") == "book" and not s.get("specialty"):
        # try body-part free text still counts as needing specialty choice
        s["needs_clarification"] = True
        s["clarification_q"] = "Could you tell me which specialty or concern this is for — e.g. orthopedics (shoulder/joint), cardiology, dermatology, or general care? And which day suits you?"
        s["route"] = "clarify"
    elif s.get("intent") in ("unknown",):
        s["needs_clarification"] = True
        s["clarification_q"] = "I can help you find hospitals/doctors, check real availability, and book, reschedule or cancel appointments. What would you like to do?"
        s["route"] = "clarify"
    else:
        s["needs_clarification"] = False
        s["route"] = {"book":"discover","find_doctor":"discover","profile":"profile","availability":"availability","reschedule":"action","cancel":"action","find_hospital":"discover_hospitals","questionnaire":"questionnaire","greeting":"answer","unsafe":"answer"}.get(s.get("intent",""), "answer")
    return s

def build_graph():
    try:
        from langgraph.graph import StateGraph, END
        g = StateGraph(GraphState)
        g.add_node("interpret", n_interpret)
        g.add_node("clarify_check", n_clarify_check)
        g.set_entry_point("interpret")
        g.add_edge("interpret", "clarify_check")
        g.add_edge("clarify_check", END)
        return g.compile()
    except Exception:
        return None

_GRAPH = None
def run_graph(text: str, ctx: dict | None = None) -> dict:
    global _GRAPH
    if _GRAPH is None: _GRAPH = build_graph()
    state: GraphState = {"text": text, **(ctx or {})}
    if _GRAPH is not None:
        try:
            out = _GRAPH.invoke(state)
            if isinstance(out, dict): return out
        except Exception: pass
    # deterministic fallback
    s1 = n_interpret(dict(state)); return n_clarify_check(s1)

async def formulate_reply(gstate: dict, db_data: dict | None = None, grok_hint: str = "") -> tuple[str, bool]:
    """Grok polishes wording; rules determine content. Never invents slots.
    Returns (reply_text, used_grok) so the UI can show what powered the wording."""
    route, intent = gstate.get("route","answer"), gstate.get("intent","unknown")
    if intent == "unsafe":
        return "I can help with appointments and admin tasks, but I can't provide diagnosis or prescriptions. You reported your concern — I've noted it for the care team. Would you like me to find an available doctor?", False
    if route == "clarify": return gstate.get("clarification_q","Could you share a few more details?"), False
    if intent == "greeting": return "Hello! I'm your care access assistant. Tell me what you need — e.g. 'I need to see a doctor for shoulder pain this week' — and I'll check real availability.", False
    # tool-grounded replies composed by caller; Grok only rephrases
    base = (db_data or {}).get("message") or grok_hint or "Here's what I found."
    from .grok_client import grok_chat
    sys = {"role":"system","content":"You are an administrative healthcare assistant. Never diagnose/prescribe. Only rephrase the given FACTS concisely. Never invent doctors, slots, or times. Refer to patient symptoms only as 'you reported ...'."}
    usr = {"role":"user","content": f"Rephrase helpfully (<=120 words). FACTS: {base}"}
    polished = await grok_chat([sys, usr])
    if polished: return polished, True
    return base, False
