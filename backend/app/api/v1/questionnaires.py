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
    _validate_schema(body.get("schema", []))
    x = models.Questionnaire(hospital_id=hid, title=body["title"], description=body.get("description",""), category=body.get("category","pre_visit"), doctor_id=body.get("doctor_id"), appointment_type_id=body.get("appointment_type_id"), schema_json=json.dumps(body.get("schema",[])), is_active=True)
    db.add(x); db.commit(); db.refresh(x)
    audit(db, "questionnaire.create", "questionnaire", x.id, hid, u.id, {"title": x.title}, "")
    return {"id": x.id}

ALLOWED_QTYPES = {"yes_no", "choice", "multi", "numeric", "date", "short_text", "long_text", "structured"}

def _validate_schema(schema):
    if not isinstance(schema, list) or not schema: raise HTTPException(400, "schema must be a non-empty list of questions")
    if len(schema) > 40: raise HTTPException(400, "schema limited to 40 questions")
    for i, q in enumerate(schema):
        if not isinstance(q, dict) or not q.get("id") or not q.get("label"): raise HTTPException(400, f"question {i}: id and label are required")
        if q.get("type") not in ALLOWED_QTYPES: raise HTTPException(400, f"question {q.get('id')}: type must be one of {sorted(ALLOWED_QTYPES)}")
        if q.get("type") in ("choice", "multi") and (not isinstance(q.get("options"), list) or not q["options"]): raise HTTPException(400, f"question {q.get('id')}: options list is required")
        low = f"{q.get('id','')} {q.get('label','')}".lower()
        if any(w in low for w in ["diagnos", "prescrib", "treatment plan", "dosage"]): raise HTTPException(400, f"question {q.get('id')}: clinical decision content is not allowed (admin info only)")

@router.patch("/questionnaires/{qid}")
def patch_q(qid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    x = db.query(models.Questionnaire).filter(models.Questionnaire.id==qid).first()
    if not x: raise HTTPException(404)
    if u.role=="hospital_admin" and x.hospital_id!=u.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    for k in ("title", "description", "category", "doctor_id", "appointment_type_id", "is_active"):
        if k in body: setattr(x, k, body[k])
    if "schema" in body:
        _validate_schema(body["schema"]); x.schema_json = json.dumps(body["schema"])
    db.commit(); audit(db, "questionnaire.update", "questionnaire", qid, x.hospital_id, u.id, {"title": x.title}, ""); return {"ok": True}

@router.delete("/questionnaires/{qid}")
def del_q(qid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    x = db.query(models.Questionnaire).filter(models.Questionnaire.id==qid).first()
    if not x: raise HTTPException(404)
    if u.role=="hospital_admin" and x.hospital_id!=u.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    if db.query(models.QuestionnaireResponse).filter(models.QuestionnaireResponse.questionnaire_id==qid).first(): raise HTTPException(400, "Questionnaire has responses; deactivate instead")
    db.delete(x); db.commit(); audit(db, "questionnaire.delete", "questionnaire", qid, x.hospital_id, u.id, {}, ""); return {"ok": True}

@router.get("/questionnaires/{qid}")
def get_q(qid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    x = db.query(models.Questionnaire).filter(models.Questionnaire.id==qid).first()
    if not x: raise HTTPException(404)
    return {"id":x.id,"title":x.title,"description":x.description,"schema":json.loads(x.schema_json or "[]")}

@router.get("/questionnaire-responses")
def list_r(patient_id: int | None = None, appointment_id: int | None = None, questionnaire_id: int | None = None, status: str = "", db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.QuestionnaireResponse)
    if u.role=="patient": q = q.filter(models.QuestionnaireResponse.patient_id==u.patient_id)
    elif u.role == "doctor":
        # Doctors see only their own appointments' responses (all filters kept).
        if not u.doctor_id: q = q.filter(False)
        else:
            q = q.join(models.Appointment, models.Appointment.id==models.QuestionnaireResponse.appointment_id).filter(models.Appointment.doctor_id==u.doctor_id)
            if appointment_id: q = q.filter(models.QuestionnaireResponse.appointment_id==appointment_id)
            if questionnaire_id: q = q.filter(models.QuestionnaireResponse.questionnaire_id==questionnaire_id)
    else:
        # Isolation: hospital staff see only their own hospital's responses.
        if u.role == "hospital_admin" and not u.hospital_id: q = q.filter(False)
        elif u.role in ("hospital_admin", "doctor") and u.hospital_id:
            q = q.join(models.Questionnaire, models.Questionnaire.id==models.QuestionnaireResponse.questionnaire_id).filter(models.Questionnaire.hospital_id==u.hospital_id)
        if patient_id: q = q.filter(models.QuestionnaireResponse.patient_id==patient_id)
        if appointment_id: q = q.filter(models.QuestionnaireResponse.appointment_id==appointment_id)
        if questionnaire_id: q = q.filter(models.QuestionnaireResponse.questionnaire_id==questionnaire_id)
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
    r = db.query(models.QuestionnaireResponse).filter(models.QuestionnaireResponse.id==rid).first()
    if not r: raise HTTPException(404)
    r.answers_json = json.dumps(body.get("answers",{})); r.status="completed"; r.collected_via=body.get("via","web"); db.commit()
    from ...services.workflows import fire_event
    ap = db.query(models.Appointment).filter(models.Appointment.id==r.appointment_id).first() if r.appointment_id else None
    fire_event(db, "questionnaire.completed", ap.hospital_id if ap else u.hospital_id, {"response_id": r.id}, "")
    return {"id": r.id, "status": "completed"}
