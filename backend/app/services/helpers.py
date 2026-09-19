import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .. import models
def audit(db: Session, action: str, entity_type="", entity_id=None, hospital_id=None, actor=None, detail=None, corr=""):
    try:
        db.add(models.AuditEvent(actor_user_id=actor, action=action, entity_type=entity_type, entity_id=entity_id, hospital_id=hospital_id, detail=json.dumps(detail or {}), correlation_id=corr)); db.commit()
    except Exception:
        db.rollback()
def ops(db: Session, kind: str, message: str, severity="info", hospital_id=None, corr="", meta=None):
    try:
        db.add(models.OperationalEvent(kind=kind, severity=severity, message=message, hospital_id=hospital_id, correlation_id=corr, meta_json=json.dumps(meta or {}))); db.commit()
    except Exception:
        db.rollback()
def notify(db: Session, kind: str, title: str, body: str, user_id=None, hospital_id=None, ref_type="", ref_id=None, channel="in_app"):
    try:
        n = models.Notification(user_id=user_id, hospital_id=hospital_id, kind=kind, title=title, body=body, status="sent", ref_type=ref_type, ref_id=ref_id, channel=channel)
        db.add(n); db.commit(); return n
    except Exception:
        db.rollback(); return None
def transition(db: Session, appt, to: str, actor="", note="", corr=""):
    from ..scheduling.engine import can_transition, norm_status
    frm = appt.status; to = norm_status(to)
    if frm == to: return appt
    if not can_transition(frm, to): raise ValueError(f"Illegal transition {frm} -> {to}")
    appt.status = to
    db.add(models.AppointmentHistory(appointment_id=appt.id, from_status=frm, to_status=to, actor=actor, note=note, correlation_id=corr))
    db.commit(); return appt
