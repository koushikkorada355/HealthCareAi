"""MCP client: timeouts, error normalization, audit-safe invocation.

Wraps the existing application registry (`app.mcp.registry.invoke`) —
the single approved path to application tools. Never touches the DB or
EHR directly. Maps every outcome to {"ok", "code", "data"|"error"} so the
tool-result node never guesses.
"""
from __future__ import annotations

import asyncio
import time
import uuid

from .. import config


def new_tool_call_id() -> str:
    return uuid.uuid4().hex[:12]


async def invoke(db, name: str, args: dict, *, user, conversation_id=None,
                 idempotency_key: str = "", corr: str = "",
                 timeout_s: float | None = None) -> dict:
    """Invoke one allowlisted tool. Never raises — always returns a result dict.

    Codes: ok | invalid (unknown tool/bad args) | denied | timeout | failed.
    On timeout the session is rolled back so the caller can continue safely.
    """
    from app.mcp import registry as reg

    if name not in reg._IMPL:
        return {"ok": False, "code": "invalid",
                "error": f"Unknown capability {name}.", "latency_ms": 0}
    t0 = time.time()
    try:
        out = await asyncio.wait_for(
            reg.invoke(db, name, dict(args or {}), user=user,
                       conversation_id=conversation_id,
                       idempotency_key=idempotency_key, corr=corr or ""),
            timeout=(timeout_s if timeout_s is not None else config.MCP_TIMEOUT_S),
        )
        ms = int((time.time() - t0) * 1000)
        data = (out or {}).get("data", out)
        return {"ok": True, "code": "ok", "data": data, "latency_ms": ms,
                "correlation_id": (out or {}).get("correlation_id", corr or "")}
    except asyncio.TimeoutError:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "code": "timeout",
                "error": "The operation timed out — nothing was confirmed. Please retry.",
                "latency_ms": int((time.time() - t0) * 1000)}
    except PermissionError as e:
        return {"ok": False, "code": "denied", "error": str(e)[:500],
                "latency_ms": int((time.time() - t0) * 1000)}
    except ValueError as e:
        return {"ok": False, "code": "failed", "error": str(e)[:500],
                "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "code": "failed", "error": str(e)[:500],
                "latency_ms": int((time.time() - t0) * 1000)}
