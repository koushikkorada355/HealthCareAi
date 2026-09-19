from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from .config import settings
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(p: str) -> str: return pwd.hash(p)
def verify_password(p: str, h: str) -> bool: return pwd.verify(p, h)
def create_token(sub: str, role: str, hospital_id=None, extra: dict | None = None) -> str:
    payload = {"sub": sub, "role": role, "hospital_id": hospital_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)}
    if extra: payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
def decode_token(t: str) -> dict:
    return jwt.decode(t, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
