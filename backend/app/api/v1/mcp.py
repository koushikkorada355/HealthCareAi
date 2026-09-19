from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...core.deps import get_current_user
from ...core.correlation import new_corr
from ...mcp.registry import CAPABILITIES, invoke

router = APIRouter(tags=["mcp"])

@router.get("/mcp/tools")
def tools(u=Depends(get_current_user)):
    return {"tools": CAPABILITIES, "note": "AI executes actions only through these capabilities; never direct DB/EHR."}

@router.post("/mcp/invoke")
async def invoke_tool(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    try:
        return await invoke(db, body["tool"], body.get("args", {}), user=u, conversation_id=body.get("conversation_id"), idempotency_key=body.get("idempotency_key",""), corr=body.get("correlation_id") or new_corr())
    except PermissionError as e: raise HTTPException(403, str(e))
    except (ValueError, Exception) as e: raise HTTPException(400, str(e)[:500])

@router.get("/mcp/executions")
def execs(db: Session = Depends(get_db), u=Depends(get_current_user)):
    from ... import models
    q = db.query(models.CapabilityExecution).order_by(models.CapabilityExecution.id.desc()).limit(200)
    return [{"id":e.id,"name":e.name,"status":e.status,"correlation_id":e.correlation_id,"at":e.created_at.isoformat(),"error":e.error[:300]} for e in q.all()]
