from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from ...db.session import get_db
from ...core.deps import get_current_user
from ... import models

router = APIRouter(tags=["ops"])

def _scope(q, model, u):
    if u.role == "hospital_admin" and u.hospital_id and hasattr(model, "hospital_id"):
        return q.filter(model.hospital_id==u.hospital_id)
    return q

@router.get("/dashboard/platform")
def dash_platform(db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role != "platform_admin": raise HTTPException(403)
    by_status = dict(db.query(models.Hospital.status, func.count(models.Hospital.id)).group_by(models.Hospital.status).all())
    return {
        "hospitals": db.query(func.count(models.Hospital.id)).scalar(),
        "hospitals_draft": by_status.get("draft", 0),
        "hospitals_submitted": by_status.get("submitted", 0),
        "hospitals_under_review": by_status.get("under_review", 0),
        "hospitals_approved": by_status.get("approved", 0),
        "hospitals_rejected": by_status.get("rejected", 0),
        "hospitals_corrections": by_status.get("corrections_requested", 0),
        "hospitals_suspended": by_status.get("suspended", 0),
        "applications_pending": db.query(func.count(models.Hospital.id)).filter(models.Hospital.status.in_(["submitted","under_review"])).scalar(),
        "doctors": db.query(func.count(models.Doctor.id)).scalar(),
        "patients": db.query(func.count(models.Patient.id)).scalar(),
        "appointments": db.query(func.count(models.Appointment.id)).scalar(),
        "confirmed": db.query(func.count(models.Appointment.id)).filter(models.Appointment.status=="confirmed").scalar(),
        "workflows_running": db.query(func.count(models.WorkflowExecution.id)).filter(models.WorkflowExecution.status=="running").scalar(),
        "audit_events": db.query(func.count(models.AuditEvent.id)).scalar(),
    }

@router.get("/dashboard/hospital")
def dash_hospital(hospital_id: int | None = None, db: Session = Depends(get_db), u=Depends(get_current_user)):
    hid = hospital_id or u.hospital_id
    if u.role=="hospital_admin" and hid!=u.hospital_id: raise HTTPException(403)
    f = lambda q: q.filter(models.Appointment.hospital_id==hid)
    return {
        "appointments": f(db.query(func.count(models.Appointment.id))).scalar(),
        "confirmed": f(db.query(func.count(models.Appointment.id)).filter(models.Appointment.status=="confirmed")).scalar(),
        "cancelled": f(db.query(func.count(models.Appointment.id)).filter(models.Appointment.status=="cancelled")).scalar(),
        "doctors": db.query(func.count(models.Doctor.id)).filter(models.Doctor.hospital_id==hid).scalar(),
        "questionnaires_pending": db.query(func.count(models.QuestionnaireResponse.id)).join(models.Questionnaire, models.Questionnaire.id==models.QuestionnaireResponse.questionnaire_id).filter(models.Questionnaire.hospital_id==hid, models.QuestionnaireResponse.status!="completed").scalar(),
        "notifications": db.query(func.count(models.Notification.id)).filter(models.Notification.hospital_id==hid).scalar(),
    }

@router.get("/dashboard/doctor")
def dash_doctor(db: Session = Depends(get_db), u=Depends(get_current_user)):
    from datetime import datetime, timezone, timedelta
    if u.role!="doctor": raise HTTPException(403)
    today = datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    tq = db.query(models.Appointment).filter(models.Appointment.doctor_id==u.doctor_id, models.Appointment.starts_at>=today, models.Appointment.starts_at<today+timedelta(days=1))
    return {"today": tq.count(), "upcoming": db.query(func.count(models.Appointment.id)).filter(models.Appointment.doctor_id==u.doctor_id, models.Appointment.starts_at>=today, models.Appointment.status.in_(["confirmed","pending","rescheduled"])).scalar(),
            "completed": db.query(func.count(models.Appointment.id)).filter(models.Appointment.doctor_id==u.doctor_id, models.Appointment.status=="completed").scalar(),
            "questionnaires_due": db.query(func.count(models.QuestionnaireResponse.id)).join(models.Appointment, models.Appointment.id==models.QuestionnaireResponse.appointment_id).filter(models.Appointment.doctor_id==u.doctor_id, models.QuestionnaireResponse.status!="completed").scalar()}

@router.get("/dashboard/patient")
def dash_patient(db: Session = Depends(get_db), u=Depends(get_current_user)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    up = db.query(models.Appointment).filter(models.Appointment.patient_id==u.patient_id, models.Appointment.starts_at>=now, ~models.Appointment.status.in_(("cancelled","completed","no_show","failed"))).order_by(models.Appointment.starts_at).first()
    d = db.query(models.Doctor).filter(models.Doctor.id==up.doctor_id).first() if up else None
    return {"upcoming": {"id":up.id,"starts_at":up.starts_at.isoformat(),"status":up.status,"doctor":d.name if d else ""} if up else None,
            "total": db.query(func.count(models.Appointment.id)).filter(models.Appointment.patient_id==u.patient_id).scalar(),
            "questionnaires_due": db.query(func.count(models.QuestionnaireResponse.id)).filter(models.QuestionnaireResponse.patient_id==u.patient_id, models.QuestionnaireResponse.status!="completed").scalar()}



@router.get("/audit")
def auditlog(db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    q = db.query(models.AuditEvent).order_by(models.AuditEvent.id.desc())
    q = _scope(q, models.AuditEvent, u)
    return [{"id":a.id,"action":a.action,"entity":a.entity_type,"entity_id":a.entity_id,"correlation_id":a.correlation_id,"at":a.created_at.isoformat()} for a in q.limit(200).all()]

@router.get("/ops/events")
def ops_events(severity: str = "", db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    q = db.query(models.OperationalEvent).order_by(models.OperationalEvent.id.desc())
    if severity: q = q.filter(models.OperationalEvent.severity==severity)
    return [{"id":e.id,"kind":e.kind,"severity":e.severity,"message":e.message,"correlation_id":e.correlation_id,"at":e.created_at.isoformat()} for e in q.limit(200).all()]

@router.get("/activity")
def activity(db: Session = Depends(get_db), u=Depends(get_current_user)):
    """Activity feed: audits + ops events.

    Platform: everything. Hospital admin: own hospital. Doctor: only rows
    touching them (own actions, own doctor record, own appointments).
    """
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    hid = u.hospital_id
    if u.role == "doctor":
        own_appts = [r[0] for r in db.query(models.Appointment.id).filter(models.Appointment.doctor_id == u.doctor_id).all()] if u.doctor_id else []
        aq = db.query(models.AuditEvent).filter(
            (models.AuditEvent.actor_user_id == u.id) |
            ((models.AuditEvent.entity_type == "doctor") & (models.AuditEvent.entity_id == u.doctor_id)) |
            ((models.AuditEvent.entity_type == "appointment") & (models.AuditEvent.entity_id.in_(own_appts) if own_appts else False))
        ).order_by(models.AuditEvent.id.desc())
        acts = [{"at": a.created_at.isoformat() if a.created_at else None, "kind": "audit", "text": f"{a.action} · {a.entity_type} #{a.entity_id or ''}".strip(), "actor": a.actor_user_id, "corr": a.correlation_id} for a in aq.limit(100).all()]
        acts.sort(key=lambda x: x["at"] or "", reverse=True)
        return acts[:120]
    aq = db.query(models.AuditEvent).order_by(models.AuditEvent.id.desc())
    oq = db.query(models.OperationalEvent).order_by(models.OperationalEvent.id.desc())
    if u.role == "hospital_admin" and hid:
        aq = aq.filter(models.AuditEvent.hospital_id == hid)
        oq = oq.filter(models.OperationalEvent.hospital_id == hid)
    acts = []
    for a in aq.limit(100).all():
        acts.append({"at": a.created_at.isoformat() if a.created_at else None, "kind": "audit", "text": f"{a.action} · {a.entity_type} #{a.entity_id or ''}".strip(), "actor": a.actor_user_id, "corr": a.correlation_id})
    for e in oq.limit(100).all():
        acts.append({"at": e.created_at.isoformat() if e.created_at else None, "kind": e.kind, "severity": e.severity, "text": e.message, "corr": e.correlation_id})
    acts.sort(key=lambda x: x["at"] or "", reverse=True)
    return acts[:120]

@router.get("/analytics/overview")
def analytics(db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    q = db.query(models.Appointment.status, func.count(models.Appointment.id)).group_by(models.Appointment.status)
    if u.role == "hospital_admin" and u.hospital_id:
        q = q.filter(models.Appointment.hospital_id == u.hospital_id)
    return {"appointments_by_status": {k:v for k,v in q.all()}}

@router.get("/patients")
def patients(db: Session = Depends(get_db), u=Depends(get_current_user), q: str = ""):
    if u.role not in ("platform_admin","hospital_admin","doctor"): raise HTTPException(403)
    query = db.query(models.Patient)
    if q: query = query.filter(models.Patient.full_name.ilike(f"%{q}%"))
    return [{"id":p.id,"full_name":p.full_name,"email":p.email,"phone":p.phone} for p in query.limit(100).all()]

@router.get("/users/me/context")
def myctx(db: Session = Depends(get_db), u=Depends(get_current_user)):
    from ...services import profile_svc as _svc
    return _svc.get_prefs(db, user=u)

@router.put("/users/me/context")
def putctx(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    import json
    from ...services import profile_svc as _svc
    try:
        prefs = body.get("prefs", body) if isinstance(body, dict) else {}
        return _svc.update_prefs(db, {"prefs": prefs}, user=u)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/users/me/profile")
def myprofile(db: Session = Depends(get_db), u=Depends(get_current_user)):
    """Own editable profile. Email is the immutable login/audit key."""
    out = {"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name, "hospital_id": u.hospital_id, "doctor_id": u.doctor_id, "patient_id": u.patient_id}
    if u.role == "patient" and u.patient_id:
        p = db.query(models.Patient).filter(models.Patient.id == u.patient_id).first()
        if p: out["patient"] = {"phone": p.phone, "dob": p.dob, "gender": p.gender, "address": p.address, "home_latitude": p.home_latitude, "home_longitude": p.home_longitude}
    return out

@router.patch("/users/me")
def patchme(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    """Self-service profile edit (email locked). Syncs users + patients rows."""
    from ...services.helpers import audit
    if "full_name" in body:
        name = (body["full_name"] or "").strip()
        if not name: raise HTTPException(400, "full_name is required")
        u.full_name = name[:255]
    if u.role == "patient" and u.patient_id:
        p = db.query(models.Patient).filter(models.Patient.id == u.patient_id).first()
        if p:
            if "full_name" in body: p.full_name = u.full_name
            if "phone" in body: p.phone = (body["phone"] or "")[:64]
            if "dob" in body: p.dob = (body["dob"] or "")[:32]
            if "gender" in body: p.gender = (body["gender"] or "")[:32]
            if "address" in body: p.address = (body["address"] or "")[:2000]
            for k, lo, hi in (("home_latitude", -90, 90), ("home_longitude", -180, 180)):
                if k in body:
                    if body[k] is None or body[k] == "":
                        setattr(p, k, None)
                    else:
                        try: v = float(body[k])
                        except (TypeError, ValueError): raise HTTPException(400, f"{k} must be a number")
                        if not (lo <= v <= hi): raise HTTPException(400, f"{k} out of range")
                        setattr(p, k, v)
    db.commit()
    audit(db, "user.update.self", "user", u.id, u.hospital_id, u.id, {"fields": sorted(body.keys())}, "")
    return {"ok": True}
