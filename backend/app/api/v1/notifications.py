from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...core.deps import get_current_user
from ... import models

router = APIRouter(tags=["notifications"])

@router.get("/notifications")
def list_n(db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.Notification)
    if u.role == "patient": q = q.filter(models.Notification.user_id==u.id)
    elif u.role == "doctor": q = q.filter(models.Notification.user_id==u.id)
    elif u.role == "hospital_admin" and u.hospital_id: q = q.filter(models.Notification.hospital_id==u.hospital_id)
    return [{"id":n.id,"kind":n.kind,"title":n.title,"body":n.body,"status":n.status,"channel":n.channel,"at":n.created_at.isoformat()} for n in q.order_by(models.Notification.id.desc()).limit(100).all()]
