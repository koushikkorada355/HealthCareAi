"""New patient capabilities: generic executors, no per-tool branches."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.ai_assistant.mcp import registry as reg
from app.db.base import Base


def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _mk(db):
    h = models.Hospital(name="CityCare", slug="citycare", status="approved",
                        address="1 Main", city="Hyd", phone="123",
                        operating_hours=json.dumps({"mon": "9-5"}),
                        services=json.dumps(["ER", "Ortho"]))
    db.add(h)
    db.commit()
    sp = models.Specialty(hospital_id=h.id, name="Cardiology")
    db.add(sp)
    dept = models.Department(hospital_id=h.id, name="Heart", description="d")
    db.add(dept)
    db.commit()
    d = models.Doctor(hospital_id=h.id, specialty_id=sp.id, department_id=dept.id,
                      name="Dr Heart", status="active", duration_minutes=30)
    db.add(d)
    db.commit()
    c = models.Calendar(hospital_id=h.id, doctor_id=d.id, name="M", is_active=True,
                        working_hours=json.dumps({"mon": [["09:00", "17:00"]]}))
    db.add(c)
    db.commit()
    for wd in range(5):
        db.add(models.AvailabilityRule(calendar_id=c.id, weekday=wd,
                                       start_time="09:00", end_time="12:00",
                                       slot_minutes=30))
    db.commit()
    at = models.AppointmentType(hospital_id=h.id, name="General",
                                duration_minutes=30, modes='["in_person"]')
    db.add(at)
    db.commit()
    qn = models.Questionnaire(hospital_id=h.id, title="Intake",
                             schema_json=json.dumps([{"id": "q1", "label": "Pain?",
                                                      "type": "yes_no"}]),
                             is_active=True)
    db.add(qn)
    db.commit()
    p = models.Patient(full_name="Pat", email="p@x.org")
    db.add(p)
    db.commit()

    class U:
        role = "patient"
        id = 1
        patient_id = p.id
        hospital_id = None
        email = "p@x.org"
        full_name = "Pat"
    return h, sp, dept, d, c, p, U()


def _run(coro):
    return asyncio.run(coro)


def test_catalog_has_34_tools():
    assert len(reg.tool_names()) == 34, reg.tool_names()
    for t in ("find_next_available", "get_hospital_info", "list_specialties",
              "list_departments", "list_appointment_types",
              "get_appointment_details", "submit_review", "get_my_profile",
              "update_my_profile", "get_my_dashboard", "list_questionnaires"):
        assert t in reg.tool_names()


def test_no_per_tool_branches_outside_registry():
    import pathlib
    import re
    new_tools = ["find_next_available", "get_hospital_info", "list_specialties",
                 "list_departments", "list_appointment_types",
                 "get_appointment_details", "submit_review", "get_my_profile",
                 "update_my_profile", "get_my_dashboard", "list_questionnaires"]
    root = pathlib.Path(__file__).resolve().parents[1] / "ai_assistant"
    bad = []
    for f in root.rglob("*.py"):
        if f.name == "registry.py":
            continue
        txt = f.read_text()
        for t in new_tools:
            if re.search(rf'["\']{t}["\']', txt):
                bad.append(f"{f.name}:{t}")
    assert bad == [], f"per-tool branches found: {bad}"


def test_generic_taxonomy_lists():
    db = _db()
    h, sp, dept, d, c, p, u = _mk(db)
    out = _run(reg.invoke(db, "list_specialties", {"hospital_id": h.id}, user=u))
    assert out["ok"] and any(s["name"] == "Cardiology" for s in out["data"]["specialties"])
    out = _run(reg.invoke(db, "list_departments", {"hospital_id": h.id}, user=u))
    assert out["ok"] and out["data"]["departments"][0]["name"] == "Heart"
    out = _run(reg.invoke(db, "list_appointment_types", {"hospital_id": h.id}, user=u))
    assert out["ok"] and out["data"]["appointment_types"][0]["name"] == "General"
    out = _run(reg.invoke(db, "list_questionnaires", {"hospital_id": h.id}, user=u))
    assert out["ok"] and out["data"]["questionnaires"][0]["title"] == "Intake"


def test_hospital_info_and_dashboard_and_profile():
    db = _db()
    h, sp, dept, d, c, p, u = _mk(db)
    out = _run(reg.invoke(db, "get_hospital_info", {"hospital_id": h.id}, user=u))
    assert out["ok"]
    assert out["data"]["services"] == ["ER", "Ortho"]
    assert out["data"]["specialties"][0]["name"] == "Cardiology"
    out = _run(reg.invoke(db, "get_my_profile", {}, user=u))
    assert out["ok"] and out["data"]["patient"]["phone"] == ""
    out = _run(reg.invoke(db, "update_my_profile", {"phone": "999", "address": "A"}, user=u))
    assert out["ok"] and "phone" in out["data"]["updated"]
    out = _run(reg.invoke(db, "get_my_dashboard", {}, user=u))
    assert out["ok"] and out["data"]["total"] == 0


def test_find_next_available_needs_scope_and_returns_real_slots():
    db = _db()
    h, sp, dept, d, c, p, u = _mk(db)
    try:
        _run(reg.invoke(db, "find_next_available", {}, user=u))
        assert False, "must require specialty/hospital"
    except ValueError:
        pass
    # next weekday
    day = datetime.now(timezone.utc) + timedelta(days=1)
    while day.weekday() > 4:
        day += timedelta(days=1)
    out = _run(reg.invoke(db, "find_next_available",
                          {"specialty": "Cardiology",
                           "date": day.date().isoformat(), "days": 3, "limit": 5},
                          user=u))
    assert out["ok"] and len(out["data"]["slots"]) > 0
    assert out["data"]["slots"][0]["doctor_id"] == d.id


def test_appt_details_review_flow():
    db = _db()
    h, sp, dept, d, c, p, u = _mk(db)
    s = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=10, minute=0,
                                                                 second=0, microsecond=0)
    while s.weekday() > 4:
        s += timedelta(days=1)
    ap = models.Appointment(hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
                            calendar_id=c.id, starts_at=s,
                            ends_at=s + timedelta(minutes=30), status="completed",
                            idempotency_key="rv1", correlation_id="c1")
    db.add(ap)
    db.commit()
    out = _run(reg.invoke(db, "get_appointment_details",
                          {"appointment_id": ap.id}, user=u))
    assert out["ok"] and "history" in out["data"] and "verifications" in out["data"]
    out = _run(reg.invoke(db, "submit_review",
                          {"appointment_id": ap.id, "target_type": "doctor",
                           "rating": 5, "title": "Great"}, user=u))
    assert out["ok"] and out["data"]["rating"] == 5
    # duplicate rejected
    try:
        _run(reg.invoke(db, "submit_review",
                        {"appointment_id": ap.id, "target_type": "doctor",
                         "rating": 4}, user=u))
        assert False, "duplicate must fail"
    except ValueError as e:
        assert "already has" in str(e)


def test_list_filters():
    db = _db()
    h, sp, dept, d, c, p, u = _mk(db)
    s = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=10, minute=0,
                                                                 second=0, microsecond=0)
    ap = models.Appointment(hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
                            calendar_id=c.id, starts_at=s,
                            ends_at=s + timedelta(minutes=30), status="cancelled",
                            idempotency_key="f1", correlation_id="c1")
    db.add(ap)
    db.commit()
    # upcoming=true hides cancelled even if in future
    out = _run(reg.invoke(db, "list_my_appointments", {"upcoming": "true"}, user=u))
    assert out["ok"] and all(x["status"] != "cancelled" for x in out["data"]["appointments"])
    out = _run(reg.invoke(db, "list_my_appointments", {"status": "cancelled"}, user=u))
    assert out["ok"] and len(out["data"]["appointments"]) == 1
