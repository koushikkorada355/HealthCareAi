from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...core.security import hash_password, verify_password, create_token
from ...core.deps import get_current_user
from ... import models
from ...services.helpers import audit
import json

router = APIRouter(tags=["auth"])

class Register(BaseModel):
    email: EmailStr; password: str; full_name: str; role: str = "patient"; hospital_id: int | None = None; phone: str = ""
class Login(BaseModel):
    email: EmailStr; password: str

def _tok(u):
    return {"access_token": create_token(str(u.id), u.role, u.hospital_id), "token_type": "bearer",
            "user": {"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name, "hospital_id": u.hospital_id, "doctor_id": u.doctor_id, "patient_id": u.patient_id}}

@router.post("/auth/register")
def register(b: Register, db: Session = Depends(get_db)):
    # Public signup: patients, hospital admins and doctors. Doctors sign up
    # unbound (no profile yet); a hospital admin adopts them by login email
    # and they accept in the doctor phase. Platform admins are seeded.
    # Hospital binding happens only at /hospitals/apply, never from this payload.
    if b.role not in ("patient","hospital_admin","doctor"): raise HTTPException(400, "Public registration is open for patient, hospital admin and doctor accounts")
    if db.query(models.User).filter(models.User.email==b.email).first(): raise HTTPException(400, "Email exists")
    u = models.User(email=b.email, password_hash=hash_password(b.password), role=b.role, full_name=b.full_name, hospital_id=None)
    db.add(u); db.commit(); db.refresh(u)
    if b.role == "patient":
        p = models.Patient(full_name=b.full_name, email=b.email, phone=b.phone); db.add(p); db.commit(); db.refresh(p)
        u.patient_id = p.id; db.commit()
        db.add(models.UserContextPref(user_id=u.id, prefs=json.dumps({"channel":"web"}))); db.commit()
    audit(db, "auth.register", "user", u.id, None, u.id, {"role": b.role}, "")
    return _tok(u)

@router.post("/auth/login")
def login(b: Login, db: Session = Depends(get_db)):
    u = db.query(models.User).filter(models.User.email==b.email).first()
    if not u or not verify_password(b.password, u.password_hash): raise HTTPException(401, "Invalid credentials")
    if not u.is_active: raise HTTPException(403, "Inactive")
    audit(db, "auth.login", "user", u.id, u.hospital_id, u.id, {}, "")
    return _tok(u)

@router.get("/auth/me")
def me(u=Depends(get_current_user)):
    return {"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name, "hospital_id": u.hospital_id, "doctor_id": u.doctor_id, "patient_id": u.patient_id}

@router.post("/auth/password-recovery")
def recover(body: dict, db: Session = Depends(get_db)):
    return {"ok": True, "message": "If the account exists, a reset link was sent (mock)."}
