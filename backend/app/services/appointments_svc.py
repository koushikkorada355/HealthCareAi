"""Appointment business logic shared by REST and MCP."""
from __future__ import annotations

from datetime import datetime, timezone

from app import models
from app.services.guards import own_appointment, serialize_appointment, uid


def list_mine(db, a, user=None):
    q = db.query(models.Appointment)
    if user and getattr(user, "role", "") == "patient":
        q = q.filter(models.Appointment.patient_id == user.patient_id)
    elif user and getattr(user, "role", "") == "doctor":
        q = q.filter(models.Appointment.doctor_id == user.doctor_id)
    elif user and getattr(user, "role", "") == "hospital_admin" and getattr(user, "hospital_id", None):
        q = q.filter(models.Appointment.hospital_id == user.hospital_id)
    if a.get("status"):
        q = q.filter(models.Appointment.status == str(a["status"]))
    if str(a.get("upcoming", "")).lower() in ("1", "true", "yes"):
        now = datetime.now(timezone.utc)
        q = q.filter(models.Appointment.starts_at >= now)
        q = q.filter(~models.Appointment.status.in_(("cancelled", "completed", "no_show", "failed")))
    rows = q.order_by(models.Appointment.starts_at.desc()).limit(20).all()
    return {"appointments": [serialize_appointment(db, r) for r in rows]}


def get_one(db, a, user=None):
    ap = own_appointment(db, a["appointment_id"], user)
    return serialize_appointment(db, ap)


def get_details(db, a, user=None):
    ap = own_appointment(db, a["appointment_id"], user)
    data = serialize_appointment(db, ap)
    data["history"] = [{"from": h.from_status, "to": h.to_status, "actor": h.actor,
                        "note": h.note, "at": h.created_at.isoformat() if h.created_at else None}
                       for h in db.query(models.AppointmentHistory).filter(
                           models.AppointmentHistory.appointment_id == ap.id).order_by(
                           models.AppointmentHistory.created_at).all()]
    data["verifications"] = []
    return data


async def create(db, a, user=None, corr="", idem="", conversation_id=None):
    for k in ("hospital_id", "doctor_id", "patient_id", "starts_at", "ends_at"):
        if not a.get(k):
            raise ValueError(f"{k} is required")
    if user and getattr(user, "role", "") == "patient" and int(a["patient_id"]) != user.patient_id:
        raise PermissionError("Cannot book for another patient")
    from app.services.guards import scope_check
    scope_check(user, a.get("hospital_id"))
    from app.services.booking import book_appointment
    return await book_appointment(
        db, hospital_id=int(a["hospital_id"]), doctor_id=int(a["doctor_id"]),
        patient_id=int(a["patient_id"]), starts_at=a["starts_at"], ends_at=a["ends_at"],
        calendar_id=a.get("calendar_id"), mode=a.get("mode", "in_person"),
        reason=a.get("reason", ""), idempotency_key=idem or a.get("idempotency_key", ""),
        actor_user_id=uid(user), conversation_id=conversation_id, corr=corr)


async def reschedule(db, a, user=None, corr=""):
    if not a.get("appointment_id") or not a.get("new_starts_at") or not a.get("new_ends_at"):
        raise ValueError("appointment_id, new_starts_at, new_ends_at are required")
    from datetime import datetime as _dt
    from app.scheduling.engine import validate_slot
    from app.services.helpers import transition
    from app.services.workflows import fire_event
    ap = own_appointment(db, a["appointment_id"], user)
    ns = _dt.fromisoformat(str(a["new_starts_at"]).replace("Z", "+00:00"))
    ne = _dt.fromisoformat(str(a["new_ends_at"]).replace("Z", "+00:00"))
    validate_slot(db, ap.doctor_id, ap.calendar_id, ns, ne, ignore_appointment_id=ap.id)
    old = ap.starts_at.isoformat()
    ap.starts_at, ap.ends_at = ns, ne
    try:
        transition(db, ap, "rescheduled", actor=f"user:{uid(user)}",
                   note=f"{old} -> {ns.isoformat()}", corr=corr)
    except Exception:
        db.rollback()
        raise
    fire_event(db, "appointment.rescheduled", ap.hospital_id, {"appointment_id": ap.id}, corr)
    db.refresh(ap)
    return {"id": ap.id, "status": ap.status, "starts_at": ap.starts_at.isoformat()}


async def cancel(db, a, user=None, corr=""):
    if not a.get("appointment_id"):
        raise ValueError("appointment_id is required")
    from app.services.helpers import transition
    from app.services.workflows import fire_event
    ap = own_appointment(db, a["appointment_id"], user)
    transition(db, ap, "cancelled", actor=f"user:{uid(user)}",
               note=a.get("reason", "cancelled"), corr=corr)
    fire_event(db, "appointment.cancelled", ap.hospital_id, {"appointment_id": ap.id}, corr)
    db.refresh(ap)
    return {"id": ap.id, "status": ap.status}
