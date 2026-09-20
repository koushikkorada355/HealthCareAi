"""MCP client: timeout + normalized results + tool_call_id."""
from __future__ import annotations

import asyncio
import time
import uuid


def new_tool_call_id() -> str:
    return uuid.uuid4().hex[:12]


async def invoke(db, name: str, args: dict, *, user, conversation_id=None,
                 idempotency_key: str = "", corr: str = "",
                 timeout_s: float | None = None) -> dict:
    from app.ai_assistant.mcp import registry as reg
    from app.core.config import settings

    timeout_s = timeout_s or 25
    t0 = time.time()
    try:
        out = await asyncio.wait_for(
            reg.invoke(db, name, args, user=user, conversation_id=conversation_id,
                       idempotency_key=idempotency_key, corr=corr),
            timeout=timeout_s)
        out["latency_ms"] = int((time.time() - t0) * 1000)
        return out
    except PermissionError as e:
        return {"ok": False, "code": "denied", "error": str(e)[:500],
                "latency_ms": int((time.time() - t0) * 1000)}
    except asyncio.TimeoutError:
        return {"ok": False, "code": "timeout",
                "error": "Capability timed out — nothing was confirmed.",
                "latency_ms": int((time.time() - t0) * 1000)}
    except ValueError as e:
        return {"ok": False, "code": "invalid", "error": str(e)[:500],
                "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "code": "failed", "error": str(e)[:500],
                "latency_ms": int((time.time() - t0) * 1000)}
