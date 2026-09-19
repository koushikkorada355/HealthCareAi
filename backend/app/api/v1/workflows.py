from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...core.deps import get_current_user
from ... import models
import json

router = APIRouter(tags=["workflows"])

@router.get("/workflows")
def list_w(hospital_id: int | None = None, db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.Workflow)
    if u.role in ("hospital_admin",) and u.hospital_id: q = q.filter((models.Workflow.hospital_id==u.hospital_id)|(models.Workflow.hospital_id==None))
    elif hospital_id: q = q.filter(models.Workflow.hospital_id==hospital_id)
    return [{"id":w.id,"name":w.name,"trigger_event":w.trigger_event,"is_active":w.is_active,"hospital_id":w.hospital_id,"steps":json.loads(w.steps_json or "[]")} for w in q.limit(100).all()]

@router.post("/workflows")
def create_w(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    w = models.Workflow(hospital_id=body.get("hospital_id") or u.hospital_id, name=body["name"], trigger_event=body["trigger_event"], steps_json=json.dumps(body.get("steps",[])), is_active=True)
    db.add(w); db.commit(); db.refresh(w); return {"id": w.id}

ALLOWED_WF_TRIGGERS = {"appointment.booked", "appointment.cancelled", "appointment.rescheduled", "questionnaire.completed", "reconciliation.required", "hospital.approved", "ehr.recovered"}

@router.patch("/workflows/{wid}")
def patch_w(wid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    from ...services.helpers import audit
    w = db.query(models.Workflow).filter(models.Workflow.id==wid).first()
    if not w: raise HTTPException(404)
    if u.role=="hospital_admin" and w.hospital_id not in (None, u.hospital_id): raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    # Catalog mode: fixed triggers, toggle + notify-step text only. No custom triggers.
    if "trigger_event" in body and body["trigger_event"] not in ALLOWED_WF_TRIGGERS: raise HTTPException(400, "Unknown trigger event")
    if "name" in body: w.name = body["name"]
    if "is_active" in body: w.is_active = bool(body["is_active"])
    if "steps" in body:
        if not isinstance(body["steps"], list) or len(body["steps"]) > 10: raise HTTPException(400, "steps must be a list of max 10")
        for s in body["steps"]:
            if not isinstance(s, dict) or s.get("type") not in ("notify_patient", "notify_doctor", "assign_questionnaire", "escalate"): raise HTTPException(400, "steps limited to notify_patient/notify_doctor/assign_questionnaire/escalate")
        w.steps_json = json.dumps(body["steps"])
    db.commit(); audit(db, "workflow.update", "workflow", wid, w.hospital_id, u.id, {"is_active": w.is_active}, ""); return {"ok": True}

@router.get("/workflow-executions")
def execs(status: str = "", db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.WorkflowExecution).order_by(models.WorkflowExecution.id.desc())
    # Isolation: hospital staff see only their own hospital's executions.
    if u.role in ("hospital_admin", "doctor") and u.hospital_id:
        q = q.join(models.Workflow, models.Workflow.id==models.WorkflowExecution.workflow_id).filter((models.Workflow.hospital_id==u.hospital_id)|(models.Workflow.hospital_id==None))
    if status: q = q.filter(models.WorkflowExecution.status==status)
    return [{"id":e.id,"workflow_id":e.workflow_id,"status":e.status,"trigger_ref":e.trigger_ref[:200],"correlation_id":e.correlation_id,"error":e.error[:300],"at":e.created_at.isoformat()} for e in q.limit(200).all()]

@router.post("/workflows/fire")
def fire(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    from ...services.workflows import fire_event
    from ...core.correlation import new_corr
    fire_event(db, body["event"], body.get("hospital_id") or u.hospital_id, body.get("payload",{}), new_corr())
    return {"fired": True}
