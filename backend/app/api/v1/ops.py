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
        "reconciliation_open": db.query(func.count(models.ReconciliationRecord.id)).filter(models.ReconciliationRecord.status=="open").scalar(),
        "unknown_outcome": db.query(func.count(models.IntegrationOperation.id)).filter(models.IntegrationOperation.status=="unknown_outcome").scalar(),
        "ai_conversations": db.query(func.count(models.AIConversation.id)).scalar(),
        "cap_success": db.query(func.count(models.CapabilityExecution.id)).filter(models.CapabilityExecution.status=="success").scalar(),
        "cap_failed": db.query(func.count(models.CapabilityExecution.id)).filter(models.CapabilityExecution.status=="failed").scalar(),
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
        "questionnaires_pending": db.query(func.count(models.QuestionnaireResponse.id)).filter(models.QuestionnaireResponse.status!="completed").scalar(),
        "reconciliation_open": db.query(func.count(models.ReconciliationRecord.id)).filter(models.ReconciliationRecord.hospital_id==hid, models.ReconciliationRecord.status=="open").scalar(),
        "ehr_ops_failed": db.query(func.count(models.IntegrationOperation.id)).filter(models.IntegrationOperation.hospital_id==hid, models.IntegrationOperation.status.in_(["failed","unknown_outcome"])).scalar(),
        "notifications": db.query(func.count(models.Notification.id)).filter(models.Notification.hospital_id==hid).scalar(),
        "ai_booked": f(db.query(func.count(models.Appointment.id)).filter(models.Appointment.conversation_id.isnot(None))).scalar(),
        "ai_conversations": db.query(func.count(models.AIConversation.id)).filter(models.AIConversation.hospital_id==hid).scalar(),
    }

@router.get("/dashboard/doctor")
def dash_doctor(db: Session = Depends(get_db), u=Depends(get_current_user)):
    from datetime import datetime, timezone, timedelta
    if u.role!="doctor": raise HTTPException(403)
    today = datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    tq = db.query(models.Appointment).filter(models.Appointment.doctor_id==u.doctor_id, models.Appointment.starts_at>=today, models.Appointment.starts_at<today+timedelta(days=1))
    return {"today": tq.count(), "upcoming": db.query(func.count(models.Appointment.id)).filter(models.Appointment.doctor_id==u.doctor_id, models.Appointment.starts_at>=today, models.Appointment.status.in_(["confirmed","pending","rescheduled"])).scalar(),
            "completed": db.query(func.count(models.Appointment.id)).filter(models.Appointment.doctor_id==u.doctor_id, models.Appointment.status=="completed").scalar(),
            "ai_today": tq.filter(models.Appointment.conversation_id.isnot(None)).count(),
            "questionnaires_due": db.query(func.count(models.QuestionnaireResponse.id)).join(models.Appointment, models.Appointment.id==models.QuestionnaireResponse.appointment_id).filter(models.Appointment.doctor_id==u.doctor_id, models.QuestionnaireResponse.status!="completed").scalar()}

@router.get("/dashboard/patient")
def dash_patient(db: Session = Depends(get_db), u=Depends(get_current_user)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    up = db.query(models.Appointment).filter(models.Appointment.patient_id==u.patient_id, models.Appointment.starts_at>=now).order_by(models.Appointment.starts_at).first()
    d = db.query(models.Doctor).filter(models.Doctor.id==up.doctor_id).first() if up else None
    return {"upcoming": {"id":up.id,"starts_at":up.starts_at.isoformat(),"status":up.status,"doctor":d.name if d else ""} if up else None,
            "total": db.query(func.count(models.Appointment.id)).filter(models.Appointment.patient_id==u.patient_id).scalar(),
            "questionnaires_due": db.query(func.count(models.QuestionnaireResponse.id)).filter(models.QuestionnaireResponse.patient_id==u.patient_id, models.QuestionnaireResponse.status!="completed").scalar()}

@router.get("/integrations/operations")
def ehr_ops(status: str = "", db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.IntegrationOperation).order_by(models.IntegrationOperation.id.desc())
    q = _scope(q, models.IntegrationOperation, u)
    if status: q = q.filter(models.IntegrationOperation.status==status)
    return [{"id":o.id,"kind":o.kind,"status":o.status,"ref_id":o.ref_id,"attempts":o.attempts,"error":o.error[:300],"correlation_id":o.correlation_id,"at":o.created_at.isoformat()} for o in q.limit(200).all()]

@router.get("/integrations/connections")
def conns(db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.HealthcareConnection).order_by(models.HealthcareConnection.id.desc())
    q = _scope(q, models.HealthcareConnection, u)
    return [{"id":c.id,"hospital_id":c.hospital_id,"vendor":c.vendor,"base_url":c.base_url,"status":c.status} for c in q.limit(100).all()]

@router.patch("/integrations/connections/{cid}")
def patch_conn(cid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    """Simple health-system settings edit (own hospital). No appointment ops here."""
    c = db.query(models.HealthcareConnection).filter(models.HealthcareConnection.id==cid).first()
    if not c: raise HTTPException(404)
    if u.role=="hospital_admin" and c.hospital_id!=u.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    for k in ("vendor", "base_url", "status"):
        if k in body: setattr(c, k, body[k])
    db.commit(); return {"ok": True, "id": c.id, "status": c.status}

@router.post("/integrations/connections/{cid}/test")
def test_conn(cid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    """Ping the configured base_url /health and record the result as status."""
    import httpx
    c = db.query(models.HealthcareConnection).filter(models.HealthcareConnection.id==cid).first()
    if not c: raise HTTPException(404)
    if u.role=="hospital_admin" and c.hospital_id!=u.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    ok, detail = False, ""
    try:
        r = httpx.get(f"{(c.base_url or '').rstrip('/')}/health", timeout=8)
        ok = r.status_code == 200; detail = r.text[:300]
    except Exception as e:
        detail = str(e)[:300]
    c.status = "active" if ok else "error"; db.commit()
    return {"ok": ok, "status": c.status, "detail": detail}

@router.get("/reconciliation")
def recon(status: str = "", db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    q = db.query(models.ReconciliationRecord).order_by(models.ReconciliationRecord.id.desc())
    q = _scope(q, models.ReconciliationRecord, u)
    if status: q = q.filter(models.ReconciliationRecord.status==status)
    return [{"id":r.id,"appointment_id":r.appointment_id,"issue":r.issue,"status":r.status,"resolution":r.resolution,"correlation_id":r.correlation_id,"at":r.created_at.isoformat()} for r in q.limit(200).all()]

@router.post("/reconciliation/{rid}/resolve")
def resolve(rid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    r = db.query(models.ReconciliationRecord).filter(models.ReconciliationRecord.id==rid).first()
    if not r: raise HTTPException(404)
    r.status = body.get("status","resolved"); r.resolution = body.get("resolution",""); r.assignee = u.email; db.commit()
    return {"ok": True}

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
    """Hospital activity feed: audits + ops events for the caller's hospital.

    Covers: doctor added/updated/activated, availability/calendar changes,
    questionnaire create/update, workflow changes, integration changes, reviews.
    """
    if u.role not in ("platform_admin", "hospital_admin"): raise HTTPException(403)
    hid = u.hospital_id
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
    by_status = db.query(models.Appointment.status, func.count(models.Appointment.id)).group_by(models.Appointment.status).all()
    by_cap = db.query(models.CapabilityExecution.status, func.count(models.CapabilityExecution.id)).group_by(models.CapabilityExecution.status).all()
    by_op = db.query(models.IntegrationOperation.status, func.count(models.IntegrationOperation.id)).group_by(models.IntegrationOperation.status).all()
    return {"appointments_by_status": {k:v for k,v in by_status}, "capabilities": {k:v for k,v in by_cap}, "ehr_ops": {k:v for k,v in by_op}}

@router.get("/ai/evaluation")
def ai_eval(db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role != "platform_admin": raise HTTPException(403)
    rows = db.query(models.AIEvaluation).order_by(models.AIEvaluation.id.desc()).limit(100).all()
    return [{"id":r.id,"metric":r.metric,"score":r.score,"at":r.created_at.isoformat()} for r in rows]

@router.get("/patients")
def patients(db: Session = Depends(get_db), u=Depends(get_current_user), q: str = ""):
    if u.role not in ("platform_admin","hospital_admin","doctor"): raise HTTPException(403)
    query = db.query(models.Patient)
    if q: query = query.filter(models.Patient.full_name.ilike(f"%{q}%"))
    return [{"id":p.id,"full_name":p.full_name,"email":p.email,"phone":p.phone,"external_patient_id":p.external_patient_id} for p in query.limit(100).all()]

@router.get("/users/me/context")
def myctx(db: Session = Depends(get_db), u=Depends(get_current_user)):
    import json
    row = db.query(models.UserContextPref).filter(models.UserContextPref.user_id==u.id).first()
    return {"prefs": json.loads(row.prefs) if row and row.prefs else {}}

@router.put("/users/me/context")
def putctx(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    import json
    row = db.query(models.UserContextPref).filter(models.UserContextPref.user_id==u.id).first()
    if not row: row = models.UserContextPref(user_id=u.id, prefs="{}"); db.add(row); db.commit()
    cur = json.loads(row.prefs or "{}"); cur.update(body.get("prefs", body)); row.prefs = json.dumps(cur); db.commit()
    return {"prefs": cur}
