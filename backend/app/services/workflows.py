import json
from sqlalchemy.orm import Session
from .. import models
from .helpers import notify, ops

def ensure_defaults(db: Session, hospital_id=None):
    defaults = [
        ("appointment.booked", "Booking: confirm + questionnaire + reminders", [{"type":"notify_patient"},{"type":"notify_doctor"},{"type":"assign_questionnaire"}]),
        ("appointment.cancelled", "Cancellation notices", [{"type":"notify_patient"},{"type":"notify_doctor"}]),
        ("appointment.rescheduled", "Reschedule notices", [{"type":"notify_patient"},{"type":"notify_doctor"}]),
        ("questionnaire.completed", "Notify doctor of completion", [{"type":"notify_doctor"}]),
        ("reconciliation.required", "Escalate to ops", [{"type":"escalate"}]),
        ("hospital.approved", "Welcome + setup checklist", [{"type":"notify_hospital"}]),
    ]
    for trig, name, steps in defaults:
        q = db.query(models.Workflow).filter(models.Workflow.trigger_event==trig, models.Workflow.hospital_id==hospital_id).first()
        if not q:
            db.add(models.Workflow(hospital_id=hospital_id, name=name, trigger_event=trig, steps_json=json.dumps(steps), is_active=True))
    db.commit()

def fire_event(db: Session, event: str, hospital_id, payload: dict, corr=""):
    flows = db.query(models.Workflow).filter(models.Workflow.trigger_event==event, models.Workflow.is_active==True).all()
    flows = [w for w in flows if (w.hospital_id == hospital_id or w.hospital_id is None)]
    for w in flows:
        ex = models.WorkflowExecution(workflow_id=w.id, trigger_ref=json.dumps(payload)[:500], status="running", input_json=json.dumps(payload), correlation_id=corr)
        db.add(ex); db.commit()
        try:
            steps = json.loads(w.steps_json or "[]")
            out = {"event": event, "steps": len(steps)}
            appt_id = payload.get("appointment_id")
            appt = db.query(models.Appointment).filter(models.Appointment.id==appt_id).first() if appt_id else None
            for s in steps:
                t = s.get("type")
                if t == "notify_patient" and appt:
                    pu = db.query(models.User).filter(models.User.patient_id==appt.patient_id).first()
                    notify(db, event, f"Update: {event}", f"Event {event} for appointment #{appt.id}", pu.id if pu else None, hospital_id, "appointment", appt.id)
                elif t == "notify_doctor" and appt:
                    du = db.query(models.User).filter(models.User.doctor_id==appt.doctor_id).first()
                    notify(db, event, f"Doctor update: {event}", f"Event {event} for appointment #{appt.id}", du.id if du else None, hospital_id, "appointment", appt.id)
                elif t == "assign_questionnaire" and appt:
                    from .questionnaire_svc import auto_assign
                    try: auto_assign(db, appt)
                    except Exception: pass
                elif t == "escalate":
                    ops(db, "workflow.escalation", f"Escalation for {event}", "warn", hospital_id, corr, payload)
            ex.status = "completed"; ex.output_json = json.dumps(out); db.commit()
        except Exception as e:
            ex.status = "failed"; ex.error = str(e)[:2000]; db.commit()
            ops(db, "workflow.failed", f"Workflow {w.name} failed: {e}", "error", hospital_id, corr, {})
