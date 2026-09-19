from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..db.session import get_db
from .security import decode_token
from .. import models

bearer = HTTPBearer(auto_error=False)

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    if not creds: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try: payload = decode_token(creds.credentials)
    except Exception: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
    if not user or not user.is_active: raise HTTPException(401, "User inactive")
    return user

def require_roles(*roles):
    def check(user=Depends(get_current_user)):
        if user.role not in roles: raise HTTPException(403, f"Requires role {roles}")
        return user
    return check

def tenant_hospital_id(user, claimed_hospital_id=None):
    """Enforce tenant isolation. Hospital admins/doctors locked to own hospital."""
    if user.role == "platform_admin": return claimed_hospital_id
    if user.role in ("hospital_admin", "doctor"):
        if claimed_hospital_id and int(claimed_hospital_id) != int(user.hospital_id or 0):
            raise HTTPException(403, "Cross-tenant access denied")
        return user.hospital_id
    return claimed_hospital_id
