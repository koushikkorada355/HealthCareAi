import json
from sqlalchemy.orm import Session
from .. import models
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
