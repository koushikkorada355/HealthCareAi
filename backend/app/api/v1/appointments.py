from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from ...db.session import get_db
from ...core.deps import get_current_user, tenant_hospital_id
from ...core.correlation import new_corr
from ... import models
from ...services.booking import book_appointment
from ...services.helpers import transition, audit, ops, notify

router = APIRouter(tags=["appointments"])

class BookIn(BaseModel):
    hospital_id: int; doctor_id: int; patient_id: int
    starts_at: str; ends_at: str; calendar_id: int | None = None; appointment_type_id: int | None = None
    mode: str = "in_person"; reason: str = ""; idempotency_key: str = ""; simulate: str = ""

@router.post("/appointments")
async def book(b: BookIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    corr = new_corr()
    # ownership: patients may only book for themselves; staff locked to own hospital
    if u.role == "patient" and b.patient_id != u.patient_id:
        raise HTTPException(403, "Cannot book for another patient")
    tenant_hospital_id(u, b.hospital_id if u.role != "platform_admin" else None)
    # input validation before service call (400, not 409)
    try:
        s = datetime.fromisoformat(str(b.starts_at).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(b.ends_at).replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "starts_at/ends_at must be ISO-8601 datetimes")
    if e <= s:
        raise HTTPException(400, "ends_at must be after starts_at")
    if e <= datetime.now(timezone.utc):
        raise HTTPException(400, "SLOT_PAST: Cannot book a slot in the past")
    try:
        out = await book_appointment(db, hospital_id=b.hospital_id, doctor_id=b.doctor_id, patient_id=b.patient_id, starts_at=b.starts_at, ends_at=b.ends_at, calendar_id=b.calendar_id, appointment_type_id=b.appointment_type_id, mode=b.mode, reason=b.reason, idempotency_key=b.idempotency_key, actor_user_id=u.id, simulate=b.simulate, corr=corr)
        return out
    except ValueError as e: raise HTTPException(409, str(e))

@router.get("/appointments")
def list_a(db: Session = Depends(get_db), u=Depends(get_current_user), status: str = "", upcoming: bool = False):
    q = db.query(models.Appointment)
    if u.role == "patient": q = q.filter(models.Appointment.patient_id==u.patient_id)
    elif u.role == "doctor": q = q.filter(models.Appointment.doctor_id==u.doctor_id)
    elif u.role == "hospital_admin": q = q.filter(models.Appointment.hospital_id==u.hospital_id)
    if status: q = q.filter(models.Appointment.status==status)
    if upcoming:
        now = datetime.now(timezone.utc)
        q = q.filter(models.Appointment.starts_at >= now)
    rows = q.order_by(models.Appointment.starts_at.desc()).limit(200).all()
    out = []
    for a in rows:
        d = db.query(models.Doctor).filter(models.Doctor.id==a.doctor_id).first()
        p = db.query(models.Patient).filter(models.Patient.id==a.patient_id).first()
        h = db.query(models.Hospital).filter(models.Hospital.id==a.hospital_id).first()
        out.append({"id":a.id,"status":a.status,"starts_at":a.starts_at.isoformat(),"ends_at":a.ends_at.isoformat(),"mode":a.mode,"reason":a.reason,"doctor_id":a.doctor_id,"doctor_name":d.name if d else "","patient_id":a.patient_id,"patient_name":p.full_name if p else "","hospital_id":a.hospital_id,"hospital_name":h.name if h else "","external_id":a.external_appointment_id,"integration_status":a.integration_status,"correlation_id":a.correlation_id,"via_ai":bool(a.conversation_id),"conversation_id":a.conversation_id})
    return out

@router.get("/appointments/{aid}")
def get_a(aid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    a = db.query(models.Appointment).filter(models.Appointment.id==aid).first()
    if not a: raise HTTPException(404)
    tenant_hospital_id(u, a.hospital_id if u.role!="platform_admin" else None)
    if u.role=="patient" and a.patient_id!=u.patient_id: raise HTTPException(403)
    if u.role=="doctor" and a.doctor_id!=u.doctor_id: raise HTTPException(403)
    hist = [{"from":h.from_status,"to":h.to_status,"actor":h.actor,"note":h.note,"at":h.created_at.isoformat()} for h in db.query(models.AppointmentHistory).filter(models.AppointmentHistory.appointment_id==aid).order_by(models.AppointmentHistory.created_at).all()]
    vers = [{"method":v.method,"result":v.result,"at":v.created_at.isoformat()} for v in db.query(models.IntegrationVerification).filter(models.IntegrationVerification.appointment_id==aid).all()]
    d = db.query(models.Doctor).filter(models.Doctor.id==a.doctor_id).first()
    p = db.query(models.Patient).filter(models.Patient.id==a.patient_id).first()
    return {"id":a.id,"status":a.status,"starts_at":a.starts_at.isoformat(),"ends_at":a.ends_at.isoformat(),"mode":a.mode,"reason":a.reason,"doctor_id":a.doctor_id,"doctor_name":d.name if d else "","patient_name":p.full_name if p else "","hospital_id":a.hospital_id,"external_id":a.external_appointment_id,"integration_status":a.integration_status,"correlation_id":a.correlation_id,"history":hist,"verifications":vers,"via_ai":bool(a.conversation_id),"conversation_id":a.conversation_id}

@router.post("/appointments/{aid}/reschedule")
async def resched(aid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if not body.get("new_starts_at") or not body.get("new_ends_at"):
        raise HTTPException(400, "new_starts_at and new_ends_at are required")
    try:
        from ...scheduling.engine import validate_slot
        from ...ehr.mock_client import EHRClient
        from ...services.workflows import fire_event
        corr = new_corr()
        ap = db.query(models.Appointment).filter(models.Appointment.id == aid).first()
        if not ap: raise ValueError("Not found")
        tenant_hospital_id(u, ap.hospital_id if u.role != "platform_admin" else None)
        if u.role == "patient" and ap.patient_id != u.patient_id: raise PermissionError("Not your appointment")
        if u.role == "doctor" and ap.doctor_id != u.doctor_id: raise PermissionError("Not your appointment")
        ns = datetime.fromisoformat(str(body["new_starts_at"]).replace("Z", "+00:00"))
        ne = datetime.fromisoformat(str(body["new_ends_at"]).replace("Z", "+00:00"))
        validate_slot(db, ap.doctor_id, ap.calendar_id, ns, ne, ignore_appointment_id=ap.id)
        old = ap.starts_at.isoformat()
        ap.starts_at, ap.ends_at = ns, ne
        try: transition(db, ap, "rescheduled", actor=f"user:{u.id}", note=f"{old} -> {ns.isoformat()}", corr=corr)
        except Exception: db.commit()
        if ap.external_appointment_id:
            try:
                await EHRClient().update_appointment(ap.external_appointment_id, {"starts_at": ns.isoformat(), "ends_at": ne.isoformat()})
                ap.integration_status = "synced"; db.commit()
            except Exception: ap.integration_status = "reconciliation_required"; db.commit()
        fire_event(db, "appointment.rescheduled", ap.hospital_id, {"appointment_id": ap.id}, corr)
        return {"id": ap.id, "status": ap.status, "starts_at": ap.starts_at.isoformat()}
    except PermissionError as e: raise HTTPException(403, str(e))
    except (ValueError, Exception) as e: raise HTTPException(409, str(e)[:500])

@router.post("/appointments/{aid}/cancel")
async def cancel(aid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    try:
        from ...ehr.mock_client import EHRClient
        from ...services.workflows import fire_event
        corr = new_corr()
        ap = db.query(models.Appointment).filter(models.Appointment.id == aid).first()
        if not ap: raise ValueError("Not found")
        tenant_hospital_id(u, ap.hospital_id if u.role != "platform_admin" else None)
        if u.role == "patient" and ap.patient_id != u.patient_id: raise PermissionError("Not your appointment")
        if u.role == "doctor" and ap.doctor_id != u.doctor_id: raise PermissionError("Not your appointment")
        transition(db, ap, "cancelled", actor=f"user:{u.id}", note=(body.get("reason") or "cancelled"), corr=corr)
        if ap.external_appointment_id:
            try: await EHRClient().cancel_appointment(ap.external_appointment_id)
            except Exception: pass
        fire_event(db, "appointment.cancelled", ap.hospital_id, {"appointment_id": ap.id}, corr)
        return {"id": ap.id, "status": "cancelled"}
    except PermissionError as e: raise HTTPException(403, str(e))
    except (ValueError, Exception) as e: raise HTTPException(409, str(e)[:500])

class CompleteIn(BaseModel):
    to: str = "completed"  # completed | no_show

@router.post("/appointments/{aid}/complete")
def complete(aid: int, b: CompleteIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    """Doctor/hospital staff mark a visit completed or no-show. Patients cannot."""
    if u.role not in ("doctor", "hospital_admin", "platform_admin"):
        raise HTTPException(403, "Only care staff can complete visits")
    a = db.query(models.Appointment).filter(models.Appointment.id == aid).first()
    if not a: raise HTTPException(404)
    tenant_hospital_id(u, a.hospital_id if u.role != "platform_admin" else None)
    if u.role == "doctor" and a.doctor_id != u.doctor_id: raise HTTPException(403)
    if b.to not in ("completed", "no_show"): raise HTTPException(400, "to must be completed or no_show")
    try:
        transition(db, a, b.to, actor=f"user:{u.id}", note=f"marked {b.to} by {u.role}", corr=new_corr())
    except ValueError as e:
        raise HTTPException(409, str(e))
    audit(db, f"appointment.{b.to}", "appointment", a.id, a.hospital_id, u.id, {}, a.correlation_id)
    return {"id": a.id, "status": a.status}

@router.post("/appointments/{aid}/retry-sync")
async def retry(aid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    from ...services.booking import recover_unknown_outcome
    a = db.query(models.Appointment).filter(models.Appointment.id==aid).first()
    if not a: raise HTTPException(404)
    op = db.query(models.IntegrationOperation).filter(models.IntegrationOperation.ref_id==aid).order_by(models.IntegrationOperation.id.desc()).first()
    if not op: raise HTTPException(400, "no operation to recover")
    return await recover_unknown_outcome(db, aid, op.id, new_corr())
