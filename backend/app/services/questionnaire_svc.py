import json
from sqlalchemy.orm import Session
from .. import models
from .guards import scope_check


def get_one(db: Session, a: dict, user=None):
    if not a.get("questionnaire_id"):
        raise ValueError("questionnaire_id is required")
    qn = db.query(models.Questionnaire).filter(
        models.Questionnaire.id == int(a["questionnaire_id"])).first()
    if not qn:
        raise ValueError("Questionnaire not found")
    scope_check(user, qn.hospital_id)
    return {"id": qn.id, "title": qn.title, "schema": qn.schema_json}


def submit(db: Session, a: dict, user=None):
    if not a.get("response_id"):
        raise ValueError("response_id is required")
    r = db.query(models.QuestionnaireResponse).filter(
        models.QuestionnaireResponse.id == int(a["response_id"])).first()
    if not r:
        raise ValueError("Response not found")
    if user and getattr(user, "role", "") == "patient" and r.patient_id != user.patient_id:
        raise PermissionError("Not your questionnaire")
    r.answers_json = json.dumps(a.get("answers", {}))
    r.status = "completed"
    db.commit()
    return {"id": r.id, "status": "completed"}


def lookup_patient(db: Session, a: dict, user=None):
    if user and getattr(user, "role", "") == "patient":
        p = db.query(models.Patient).filter(models.Patient.id == user.patient_id).first()
        return {"id": p.id, "full_name": p.full_name} if p else {}
    q = str(a.get("q", ""))
    rows = db.query(models.Patient).filter(models.Patient.full_name.ilike(f"%{q}%")).limit(10).all() if q else []
    return {"patients": [{"id": p.id, "full_name": p.full_name} for p in rows]}


def auto_assign(db: Session, appt):
    qs = db.query(models.Questionnaire).filter(models.Questionnaire.hospital_id==appt.hospital_id, models.Questionnaire.is_active==True).all()
    # prefer doctor-specific, else specialty/hospital
    chosen = None
    for q in qs:
        if q.doctor_id == appt.doctor_id: chosen = q; break
    if not chosen and qs: chosen = qs[0]
    if not chosen: return None
    ex = db.query(models.QuestionnaireResponse).filter(models.QuestionnaireResponse.questionnaire_id==chosen.id, models.QuestionnaireResponse.appointment_id==appt.id).first()
    if ex: return ex
    r = models.QuestionnaireResponse(questionnaire_id=chosen.id, appointment_id=appt.id, patient_id=appt.patient_id, answers_json="{}", status="assigned")
    db.add(r); db.commit(); return r
