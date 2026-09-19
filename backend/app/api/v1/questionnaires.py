from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...core.deps import get_current_user
from ... import models
from ...services.helpers import audit
import json

router = APIRouter(tags=["questionnaires"])

@router.get("/questionnaires")
def list_q(hospital_id: int | None = None, db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.Questionnaire)
    if u.role in ("hospital_admin","doctor") and u.hospital_id: q = q.filter(models.Questionnaire.hospital_id==u.hospital_id)
    elif hospital_id: q = q.filter(models.Questionnaire.hospital_id==hospital_id)
    return [{"id":x.id,"hospital_id":x.hospital_id,"title":x.title,"description":x.description,"category":x.category,"doctor_id":x.doctor_id,"is_active":x.is_active,"schema":json.loads(x.schema_json or "[]")} for x in q.limit(100).all()]

@router.post("/questionnaires")
def create_q(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    hid = body.get("hospital_id") or u.hospital_id
    if u.role=="hospital_admin" and hid!=u.hospital_id: raise HTTPException(403)
    x = models.Questionnaire(hospital_id=hid, title=body["title"], description=body.get("description",""), category=body.get("category","pre_visit"), doctor_id=body.get("doctor_id"), appointment_type_id=body.get("appointment_type_id"), schema_json=json.dumps(body.get("schema",[])), is_active=True)
    db.add(x); db.commit(); db.refresh(x)
    audit(db, "questionnaire.create", "questionnaire", x.id, hid, u.id, {"title": x.title}, "")
    return {"id": x.id}

@router.get("/questionnaires/{qid}")
def get_q(qid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    x = db.query(models.Questionnaire).filter(models.Questionnaire.id==qid).first()
    if not x: raise HTTPException(404)
    return {"id":x.id,"title":x.title,"description":x.description,"schema":json.loads(x.schema_json or "[]")}

@router.get("/questionnaire-responses")
def list_r(patient_id: int | None = None, appointment_id: int | None = None, status: str = "", db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.QuestionnaireResponse)
    if u.role=="patient": q = q.filter(models.QuestionnaireResponse.patient_id==u.patient_id)
    else:
        if patient_id: q = q.filter(models.QuestionnaireResponse.patient_id==patient_id)
        if appointment_id: q = q.filter(models.QuestionnaireResponse.appointment_id==appointment_id)
    if status: q = q.filter(models.QuestionnaireResponse.status==status)
    out = []
    for r in q.order_by(models.QuestionnaireResponse.id.desc()).limit(200).all():
        qq = db.query(models.Questionnaire).filter(models.Questionnaire.id==r.questionnaire_id).first()
        out.append({"id":r.id,"questionnaire_id":r.questionnaire_id,"questionnaire_title":qq.title if qq else "","appointment_id":r.appointment_id,"patient_id":r.patient_id,"status":r.status,"answers":json.loads(r.answers_json or "{}"),"collected_via":r.collected_via})
    return out

@router.post("/questionnaire-responses")
def create_r(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    r = models.QuestionnaireResponse(questionnaire_id=body["questionnaire_id"], appointment_id=body.get("appointment_id"), patient_id=body.get("patient_id") or u.patient_id, answers_json=json.dumps(body.get("answers",{})), status=body.get("status","assigned"), collected_via=body.get("via","web"))
    db.add(r); db.commit(); db.refresh(r); return {"id": r.id}

@router.post("/questionnaire-responses/{rid}/submit")
def submit_r(rid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    from ...mcp.registry import invoke
    import asyncio
    r = db.query(models.QuestionnaireResponse).filter(models.QuestionnaireResponse.id==rid).first()
    if not r: raise HTTPException(404)
    r.answers_json = json.dumps(body.get("answers",{})); r.status="completed"; r.collected_via=body.get("via","web"); db.commit()
    from ...services.workflows import fire_event
    ap = db.query(models.Appointment).filter(models.Appointment.id==r.appointment_id).first() if r.appointment_id else None
    fire_event(db, "questionnaire.completed", ap.hospital_id if ap else u.hospital_id, {"response_id": r.id}, "")
    return {"id": r.id, "status": "completed"}
