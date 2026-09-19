import uuid
from contextvars import ContextVar
corr: ContextVar[str] = ContextVar("corr", default="")
def new_corr() -> str:
    v = uuid.uuid4().hex[:12]; corr.set(v); return v
def get_corr() -> str: return corr.get() or uuid.uuid4().hex[:12]
