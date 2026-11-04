"""Appointment service: scheduling validation -> confirm. No external integration."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .. import models
from ..scheduling.engine import validate_slot
from .helpers import audit, ops, notify, transition
from ..core.correlation import get_corr

def _ensure_dt(v):
    if isinstance(v, datetime): return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z","+00:00"))

async def book_appointment(db: Session, *, hospital_id: int, doctor_id: int, patient_id: int, starts_at, ends_at, calendar_id=None, appointment_type_id=None, mode="in_person", reason="", idempotency_key="", actor_user_id=None, conversation_id=None, corr: str = "") -> dict:
    corr = corr or get_corr()
    idempotency_key = idempotency_key or f"book-{uuid.uuid4().hex}"
    try:
        starts_at, ends_at = _ensure_dt(starts_at), _ensure_dt(ends_at)
    except (ValueError, TypeError):
        raise ValueError("starts_at/ends_at must be ISO-8601 datetimes")
    if ends_at <= starts_at:
        raise ValueError("ends_at must be after starts_at")
    # idempotency: return existing
    ex = db.query(models.Appointment).filter(models.Appointment.idempotency_key==idempotency_key).first()
    if ex: return {"appointment_id": ex.id, "status": ex.status, "deduplicated": True, "correlation_id": corr}
    doc = db.query(models.Doctor).filter(models.Doctor.id==doctor_id).first()
    if not doc or doc.status != "active": raise ValueError("Doctor not bookable")
    hosp = db.query(models.Hospital).filter(models.Hospital.id==hospital_id).first()
    if not hosp or hosp.status != "approved": raise ValueError("Hospital not approved for booking")
    if not calendar_id:
        cal = db.query(models.Calendar).filter(models.Calendar.doctor_id==doctor_id, models.Calendar.is_active==True).first()
        if not cal: raise ValueError("No active calendar")
        calendar_id = cal.id
    try: validate_slot(db, doctor_id, calendar_id, starts_at, ends_at)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("SLOT_"):
            raise
        clash = db.query(models.Appointment).filter(models.Appointment.doctor_id==doctor_id, models.Appointment.starts_at < ends_at, models.Appointment.ends_at > starts_at, models.Appointment.status.in_(["pending","confirmed","rescheduled"])).first()
        if clash:
            raise ValueError("SLOT_TAKEN: Slot just got booked by someone else (conflict detected)")
        raise ValueError(msg)
    appt = models.Appointment(hospital_id=hospital_id, doctor_id=doctor_id, patient_id=patient_id, calendar_id=calendar_id, appointment_type_id=appointment_type_id, starts_at=starts_at, ends_at=ends_at, status="pending", mode=mode, reason=reason[:2000], idempotency_key=idempotency_key, correlation_id=corr, conversation_id=conversation_id)
    db.add(appt)
    try: db.commit(); db.refresh(appt)
    except IntegrityError:
        db.rollback()
        conflict = db.query(models.Appointment).filter(models.Appointment.doctor_id==doctor_id, models.Appointment.starts_at < ends_at, models.Appointment.ends_at > starts_at, models.Appointment.status.in_(["pending","confirmed","rescheduled"])).first()
        raise ValueError("SLOT_TAKEN: Slot just got booked by someone else (conflict detected)")
    try:
        db.add(models.AppointmentHistory(appointment_id=appt.id, from_status="", to_status="pending", actor=f"user:{actor_user_id}", note="created", correlation_id=corr)); db.commit()
    except Exception:
        db.rollback()
        raise ValueError("Booking failed before confirmation; please retry")
    # Direct confirm — no external system.
    transition(db, appt, "confirmed", actor="system", note="slot validated", corr=corr)
    audit(db, "appointment.confirmed", "appointment", appt.id, hospital_id, actor_user_id, {}, corr)
    from .workflows import fire_event
    fire_event(db, "appointment.booked", hospital_id, {"appointment_id": appt.id}, corr)
    pu = db.query(models.User).filter(models.User.patient_id==patient_id).first()
    du = db.query(models.User).filter(models.User.doctor_id==doctor_id).first()
    _n1 = notify(db, "appointment_confirmation", "Appointment confirmed", f"Your appointment with {doc.name} on {starts_at:%a %b %d, %H:%M} is confirmed.", pu.id if pu else None, hospital_id, "appointment", appt.id)
    _n2 = notify(db, "new_appointment", "New appointment", f"New booking: {starts_at:%b %d %H:%M}.", du.id if du else None, hospital_id, "appointment", appt.id) if du else None
    _q_ok = True
    try:
        from .questionnaire_svc import auto_assign
        auto_assign(db, appt)
    except Exception:
        _q_ok = False
    # Main booking is durable; side-effect shortfalls are reported as partial
    # success (additive keys) instead of silent success.
    return {"appointment_id": appt.id, "status": appt.status, "correlation_id": corr, "verified": True,
            "notified": bool(_n1), "questionnaire": "assigned" if _q_ok else "pending"}
