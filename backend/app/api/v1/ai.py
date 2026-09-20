"""Patient AI chat: DB-persisted threads, fail-closed (503 when LLM down)."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.correlation import new_corr
from ...core.deps import get_current_user
from ...db.session import get_db
from ... import models

router = APIRouter(tags=["ai"])


class ChatIn(BaseModel):
    conversation_id: int | None = None
    message: str
    channel: str = "web"


@router.post("/ai/chat")
async def chat(b: ChatIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if not (b.message or "").strip():
        raise HTTPException(400, "message is required")
    if u.role not in ("patient", "doctor", "hospital_admin", "platform_admin"):
        raise HTTPException(403, "AI chat not enabled for this role")
    corr = new_corr()
    from ...ai_assistant.services.assistant import run_turn
    from ...ai_assistant.services.llm import AINotAvailable

    try:
        return await run_turn(db, user=u, conversation_id=b.conversation_id,
                              text=b.message.strip()[:4000],
                              channel=b.channel or "web", corr=corr)
    except AINotAvailable as e:
        import logging as _logging
        _logging.getLogger("careaccess").warning("ai unavailable corr=%s err=%s", corr, str(e)[:500])
        raise HTTPException(503, f"AI unavailable — configure INCEPTION_API_KEY ({corr})")
    except (ValueError, PermissionError) as e:
        raise HTTPException(400 if isinstance(e, ValueError) else 403, str(e)[:500])


@router.get("/ai/conversations")
def list_conversations(db: Session = Depends(get_db), u=Depends(get_current_user),
                       limit: int = 20):
    q = db.query(models.AIConversation)
    if u.role == "patient":
        q = q.filter(models.AIConversation.user_id == u.id)
    elif u.role in ("hospital_admin", "doctor") and u.hospital_id:
        q = q.filter(models.AIConversation.hospital_id == u.hospital_id)
    rows = q.order_by(models.AIConversation.updated_at.desc()).limit(max(1, min(limit, 50))).all()
    out = []
    for c in rows:
        last = (db.query(models.AIMessage).filter(models.AIMessage.conversation_id == c.id)
                .order_by(models.AIMessage.id.desc()).first())
        out.append({"id": c.id, "status": c.status, "channel": c.channel,
                    "correlation_id": c.correlation_id,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                    "preview": (last.content[:120] if last else "")})
    return out


@router.get("/ai/conversations/{cid}/messages")
def get_messages(cid: int, db: Session = Depends(get_db), u=Depends(get_current_user),
                 limit: int = 50, before_id: int | None = None):
    c = db.query(models.AIConversation).filter(models.AIConversation.id == cid).first()
    if not c:
        raise HTTPException(404, "Conversation not found")
    if u.role == "patient" and c.user_id != u.id:
        raise HTTPException(403, "Not your conversation")
    if (u.role in ("hospital_admin", "doctor") and c.hospital_id and u.hospital_id
            and int(c.hospital_id) != int(u.hospital_id)):
        raise HTTPException(403, "Cross-tenant denied")
    q = db.query(models.AIMessage).filter(models.AIMessage.conversation_id == cid)
    if before_id:
        q = q.filter(models.AIMessage.id < int(before_id))
    rows = q.order_by(models.AIMessage.id.desc()).limit(max(1, min(limit, 100))).all()
    rows = list(reversed(rows))
    out = []
    for r in rows:
        data = {}
        try:
            data = json.loads(getattr(r, "data_json", "") or "") or {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        out.append({"id": r.id, "role": r.role, "content": r.content, "tool_name": r.tool_name,
                    "data": data,
                    "created_at": r.created_at.isoformat() if r.created_at else None})
    return out


@router.delete("/ai/conversations/{cid}")
def close_conversation(cid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    c = db.query(models.AIConversation).filter(models.AIConversation.id == cid).first()
    if not c:
        raise HTTPException(404, "Conversation not found")
    if u.role == "patient" and c.user_id != u.id:
        raise HTTPException(403, "Not your conversation")
    c.status = "closed"
    db.commit()
    return {"ok": True}
