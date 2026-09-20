"""MCP capability catalog for the AI layer + debug trace."""
from fastapi import APIRouter, Depends

from ...core.deps import get_current_user

router = APIRouter(tags=["mcp"])


@router.get("/mcp/tools")
def list_tools(u=Depends(get_current_user)):
    from ...ai_assistant.mcp import adapter
    from ...ai_assistant.mcp import registry as reg

    return {"tools": [{"name": t["name"], "description": t["description"],
                       "idempotent": t["idempotent"]} for t in reg.CAPABILITIES],
            "count": len(reg.CAPABILITIES)}
