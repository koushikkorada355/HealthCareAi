"""Classification prompt wording.

Guides the LLM to emit the Classification JSON shape. The schema
(schemas/classification.py) is authoritative; this text is a hint.
Deterministic fallback covers offline/misparse cases.
"""
CLASSIFY_INSTRUCTIONS = (
    "Classify the patient message for a healthcare administrative assistant. "
    "Reply with JSON only: {\"category\": one of "
    "[\"administrative\", \"clinical\", \"unrelated\", \"ambiguous\", \"unsupported\"], "
    "\"intent\": one of [\"book\", \"reschedule\", \"cancel\", \"find_doctor\", "
    "\"find_hospital\", \"profile\", \"availability\", \"questionnaire\", \"hours\", "
    "\"greeting\", \"confirm\", \"decline\", \"lookup\", \"notify\", \"escalate\", "
    "\"preferences\", \"unknown\"], "
    "\"entities\": {\"specialty\": str, \"doctor_name\": str, \"city\": str, "
    "\"date_pref\": str, \"slot_iso\": str, \"appointment_id\": int}, "
    "\"confidence\": 0.0-1.0, \"needs_action_write\": bool}. "
    "Set needs_action_write=true when the message asks to create, reschedule, "
    "cancel, submit, send, or change anything persisted. "
    "Confirmations ('yes', 'confirm', 'book it', 'go ahead') get intent confirm. "
    "Clinical content (diagnose/prescribe/dosage/treatment) gets category clinical. "
    "Non-healthcare chatter gets category unrelated."
)

FEW_SHOTS = [
    ("I need to see a doctor for shoulder pain this week",
     {"category": "administrative", "intent": "book", "entities": {"specialty": "orthopedics"}, "confidence": 0.9, "needs_action_write": False}),
    ("cancel my appointment tomorrow",
     {"category": "administrative", "intent": "cancel", "entities": {}, "confidence": 0.8, "needs_action_write": True}),
    ("yes, book it",
     {"category": "administrative", "intent": "confirm", "entities": {}, "confidence": 0.95, "needs_action_write": True}),
    ("what do I have, diagnose me",
     {"category": "clinical", "intent": "unknown", "entities": {}, "confidence": 0.9, "needs_action_write": False}),
    ("tell me a joke",
     {"category": "unrelated", "intent": "unknown", "entities": {}, "confidence": 0.9, "needs_action_write": False}),
]
