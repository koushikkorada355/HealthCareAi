"""Appointment service: scheduling validation -> EHR -> verify -> sync. Never confirm before verification."""
import json, uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .. import models
from ..scheduling.engine import validate_slot
from ..ehr.mock_client import EHRClient
from .helpers import audit, ops, notify, transition
from ..core.correlation import get_corr

def _ensure_dt(v):
    if isinstance(v, datetime): return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z","+00:00"))

async def book_appointment(db: Session, *, hospital_id: int, doctor_id: int, patient_id: int, starts_at, ends_at, calendar_id=None, appointment_type_id=None, mode="in_person", reason="", idempotency_key="", actor_user_id=None, conversation_id=None, simulate: str = "", corr: str = "") -> dict:
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
    if ex: return {"appointment_id": ex.id, "status": ex.status, "external_id": ex.external_appointment_id, "deduplicated": True, "correlation_id": corr}
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
        # Same slot taken between list and book (or on DBs without exclusion
        # enforcement): label it so callers render the rejection + alternatives.
        clash = db.query(models.Appointment).filter(models.Appointment.doctor_id==doctor_id, models.Appointment.starts_at < ends_at, models.Appointment.ends_at > starts_at, models.Appointment.status.in_(["pending","confirmed","sync_pending","rescheduled","reconciliation_required"])).first()
        if clash:
            raise ValueError("SLOT_TAKEN: Slot just got booked by someone else (conflict detected)")
        raise ValueError(msg)
    appt = models.Appointment(hospital_id=hospital_id, doctor_id=doctor_id, patient_id=patient_id, calendar_id=calendar_id, appointment_type_id=appointment_type_id, starts_at=starts_at, ends_at=ends_at, status="pending", mode=mode, reason=reason[:2000], idempotency_key=idempotency_key, correlation_id=corr, integration_status="pending", conversation_id=conversation_id)
    db.add(appt)
    try: db.commit(); db.refresh(appt)
    except IntegrityError:
        db.rollback()
        conflict = db.query(models.Appointment).filter(models.Appointment.doctor_id==doctor_id, models.Appointment.starts_at < ends_at, models.Appointment.ends_at > starts_at, models.Appointment.status.in_(["pending","confirmed","sync_pending","rescheduled","reconciliation_required"])).first()
        # Coded rejection: no row is kept, no locks are taken — the unique and
        # exclusion indexes arbitrated the race atomically at commit time.
        raise ValueError("SLOT_TAKEN: Slot just got booked by someone else (conflict detected)")
    db.add(models.AppointmentHistory(appointment_id=appt.id, from_status="", to_status="pending", actor=f"user:{actor_user_id}", note="created", correlation_id=corr)); db.commit()
    # --- EHR operation ---
    op = models.IntegrationOperation(hospital_id=hospital_id, kind="create", ref_type="appointment", ref_id=appt.id, status="started", request_json=json.dumps({"doctor": doc.external_provider_id, "starts_at": starts_at.isoformat()}), idempotency_key=idempotency_key, correlation_id=corr)
    db.add(op); db.commit()
    pat = db.query(models.Patient).filter(models.Patient.id==patient_id).first()
    ehr = EHRClient()
    payload = {"patient_ref": getattr(pat, "external_patient_id", None) or f"int-pat-{patient_id}", "patient_name": getattr(pat, "full_name", ""), "provider_id": doc.external_provider_id or f"int-doc-{doctor_id}", "facility_id": hosp.external_facility_id or f"int-fac-{hospital_id}", "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat(), "reason": reason[:500], "idempotency_key": idempotency_key}
    # failure injection for demo: simulate=timeout_after_create
    try:
        if simulate == "timeout_after_create":
            # actually create in EHR, then pretend timeout
            try: created = await ehr.create_appointment(payload, idempotency_key)
            except Exception: created = None
            raise TimeoutError("Simulated network timeout after EHR create (unknown outcome)")
        created = await ehr.create_appointment(payload, idempotency_key)
        op.status = "success"; op.response_json = json.dumps(created); db.commit()
    except TimeoutError as te:
        op.status = "unknown_outcome"; op.error = str(te); db.commit()
        return await recover_unknown_outcome(db, appt.id, op.id, corr)
    except Exception as e:
        msg = str(e)
        op.status = "failed"; op.error = msg[:2000]; db.commit()
        transition(db, appt, "failed", actor="system", note=f"EHR create failed: {msg[:300]}", corr=corr)
        appt.integration_status = "failed"; db.commit()
        audit(db, "appointment.failed", "appointment", appt.id, hospital_id, actor_user_id, {"error": msg[:500]}, corr)
        ops(db, "ehr.create.failed", f"EHR create failed appt {appt.id}", "error", hospital_id, corr, {"error": msg[:500]})
        if "409" in msg or "conflict" in msg.lower():
            raise ValueError(f"SLOT_TAKEN: External system reports a conflict: {msg[:200]}")
        raise ValueError(f"External booking failed: {msg[:300]}")
    # --- verification (mandatory before confirm) ---
    ext_id = (created or {}).get("id") or (created or {}).get("external_id")
    ver = models.IntegrationVerification(operation_id=op.id, appointment_id=appt.id, method="retrieve", result="pending", correlation_id=corr)
    db.add(ver); db.commit()
    try:
        seen = await ehr.get_appointment(ext_id)
        if seen and seen.get("id") == ext_id:
            ver.result = "matched"; ver.detail_json = json.dumps({"external": seen}); db.commit()
            op.status = "success"; db.commit()
        else:
            ver.result = "not_found"; ver.detail_json = json.dumps({"ext_id": ext_id}); db.commit()
            return await recover_unknown_outcome(db, appt.id, op.id, corr)
    except Exception as e:
        ver.result = "error"; ver.detail_json = json.dumps({"error": str(e)[:500]}); db.commit()
        return await recover_unknown_outcome(db, appt.id, op.id, corr)
    # --- sync ---
    appt.external_appointment_id = ext_id; appt.integration_status = "synced"; db.commit()
    db.add(models.ExternalIdMap(hospital_id=hospital_id, entity_type="appointment", internal_id=str(appt.id), external_id=ext_id, vendor="mock")); db.commit()
    transition(db, appt, "confirmed", actor="system", note=f"verified ext={ext_id}", corr=corr)
    audit(db, "appointment.confirmed", "appointment", appt.id, hospital_id, actor_user_id, {"ext": ext_id}, corr)
    # workflows + notifications
    from .workflows import fire_event
    fire_event(db, "appointment.booked", hospital_id, {"appointment_id": appt.id}, corr)
    pu = db.query(models.User).filter(models.User.patient_id==patient_id).first()
    du = db.query(models.User).filter(models.User.doctor_id==doctor_id).first()
    notify(db, "appointment_confirmation", "Appointment confirmed", f"Your appointment with {doc.name} on {starts_at:%a %b %d, %H:%M} is confirmed.", pu.id if pu else None, hospital_id, "appointment", appt.id)
    if du: notify(db, "new_appointment", "New appointment", f"New booking: {starts_at:%b %d %H:%M}.", du.id, hospital_id, "appointment", appt.id)
    # auto-assign questionnaire
    try:
        from .questionnaire_svc import auto_assign
        auto_assign(db, appt)
    except Exception: pass
    return {"appointment_id": appt.id, "status": appt.status, "external_id": ext_id, "correlation_id": corr, "verified": True}

async def recover_unknown_outcome(db: Session, appointment_id: int, operation_id: int, corr: str):
    """Query external system; sync safely; never duplicate."""
    from .workflows import fire_event
    appt = db.query(models.Appointment).filter(models.Appointment.id==appointment_id).first()
    op = db.query(models.IntegrationOperation).filter(models.IntegrationOperation.id==operation_id).first()
    ehr = EHRClient()
    appt.integration_status = "unknown_outcome"; db.commit()
    ops(db, "ehr.unknown_outcome", f"Unknown outcome appt {appt.id}, probing EHR", "warn", appt.hospital_id, corr, {"op": op.id})
    # probe by idempotency key via list endpoint
    found = None
    try:
        async with __import__("httpx").AsyncClient(timeout=8) as c:
            r = await c.get(f"{ehr.base}/ehr/appointments", params={"idempotency_key": op.idempotency_key}, headers=ehr._h())
            if r.status_code == 200:
                items = r.json()
                lst = items if isinstance(items, list) else items.get("items", [])
                if lst: found = lst[0]
    except Exception as e:
        pass
    if found:
        ext_id = found.get("id")
        appt.external_appointment_id = ext_id; appt.integration_status = "synced"; db.commit()
        op.status = "success"; op.response_json = json.dumps(found); db.commit()
        db.add(models.IntegrationVerification(operation_id=op.id, appointment_id=appt.id, method="probe_by_idempotency", result="matched", detail_json=json.dumps({"external": found}), correlation_id=corr)); db.commit()
        try: transition(db, appt, "confirmed", actor="system:recovery", note=f"recovered ext={ext_id}, no duplicate", corr=corr)
        except Exception: pass
        ops(db, "ehr.recovered", f"Recovered appt {appt.id} ext={ext_id} without duplicate", "info", appt.hospital_id, corr, {})
        fire_event(db, "ehr.recovered", appt.hospital_id, {"appointment_id": appt.id}, corr)
        return {"appointment_id": appt.id, "status": appt.status, "external_id": ext_id, "correlation_id": corr, "recovered": True, "verified": True}
    # not found -> safe to keep pending + reconciliation record for human
    rec = models.ReconciliationRecord(hospital_id=appt.hospital_id, appointment_id=appt.id, issue="unknown_outcome_not_found", status="open", resolution="", correlation_id=corr)
    db.add(rec)
    appt.integration_status = "reconciliation_required"; db.commit()
    try: transition(db, appt, "reconciliation_required", actor="system:recovery", note="EHR probe found nothing; needs retry/escalation", corr=corr)
    except Exception: pass
    ops(db, "reconciliation.opened", f"Reconciliation opened appt {appt.id}", "warn", appt.hospital_id, corr, {"rec": rec.id})
    fire_event(db, "reconciliation.required", appt.hospital_id, {"appointment_id": appt.id, "rec_id": rec.id}, corr)
    return {"appointment_id": appt.id, "status": appt.status, "correlation_id": corr, "recovered": False, "needs_reconciliation": True}
