"""User-friendly output: no tool calls, JSON, or internal IDs reach the user.

Global across all tools: reply text and card/UI payloads must carry only
natural conversational language and display-safe fields.
"""
from app.ai_assistant.nodes.response import sanitize_payload, sanitize_reply
from app.ai_assistant import orchestration as orch


def test_success_booking_converted_to_natural():
    raw = (
        '{"tool": "create_appointment", "data": {"doctor_id": 5, '
        '"start_at": "2026-11-04T14:30:00+00:00", "end_at": "2026-11-04T15:00:00+00:00", '
        '"calendar_id": 5, "patient_id": 1}} '
        "Your appointment has been successfully booked for November 4, 2026, at 2:30 PM."
    )
    out = sanitize_reply(raw, tool_ok=True,
                         data={"starts_at": "2026-11-04T14:30:00+00:00"})
    assert "create_appointment" not in out
    assert "doctor_id" not in out
    assert "calendar_id" not in out
    assert "patient_id" not in out
    assert "{" not in out and "}" not in out
    assert "successfully booked" in out.lower()


def test_failed_execution_hides_internals():
    raw = (
        'create_appointment failed with {"doctor_id": 5, "patient_id": 1}. '
        "Error: SLOT_TAKEN. That time was just taken."
    )
    out = sanitize_reply(raw, tool_ok=False, data={})
    assert "create_appointment" not in out
    assert "doctor_id" not in out
    assert "patient_id" not in out
    assert "just taken" in out.lower()


def test_multiple_tool_calls_all_sanitized():
    raw = (
        "search_doctors found Dr. Rao (doctor_id: 3). "
        "check_availability returned slots for calendar_id=7. "
        "Booking now."
    )
    out = sanitize_reply(raw, tool_ok=True, data={})
    assert "search_doctors" not in out
    assert "check_availability" not in out
    assert "doctor_id" not in out
    assert "calendar_id" not in out
    assert "Booking now" in out


def test_missing_information_asks_naturally():
    raw = (
        'Missing required arguments: hospital_id. '
        "Which hospital would you like?"
    )
    out = sanitize_reply(raw, tool_ok=False, data={})
    assert "hospital_id" not in out
    assert "Which hospital" in out


def test_card_payload_strips_internal_ids():
    payload = {"card": "doctors", "items": [
        {"id": 1, "name": "Dr. A", "doctor_id": 5, "hospital_id": 2,
         "calendar_id": 7, "correlation_id": "abc",
         "actions": [{"label": "Book", "text": "Book"}]},
    ]}
    clean = sanitize_payload(payload)
    item = clean["items"][0]
    assert "doctor_id" not in item
    assert "hospital_id" not in item
    assert "calendar_id" not in item
    assert "correlation_id" not in item
    assert item["name"] == "Dr. A"
    assert item["actions"] == [{"label": "Book", "text": "Book"}]


def test_orchestration_card_items_generic():
    card = orch.build_card("search_doctors", {"doctors": [
        {"id": 1, "name": "Dr. A", "doctor_id": 1, "patient_id": 9,
         "hospital_name": "City"},
    ]})
    item = card["items"][0]
    assert "doctor_id" not in item
    assert "patient_id" not in item
    assert item["name"] == "Dr. A"


def test_prompt_requires_user_friendly_rule():
    from app.ai_assistant.prompts.system import RESPONSE_SYSTEM
    assert "Never display internal tool calls" in RESPONSE_SYSTEM
    assert "doctor_id" in RESPONSE_SYSTEM
    assert "natural" in RESPONSE_SYSTEM.lower()
