"""Generic tool-execution outcomes shared by every tool.

No tool names, entities, or workflows appear here. Every execution maps to
one outcome: success | failed | partial | empty | missing | unsupported |
pending | unverified. Routers, executors, and the response layer all read
this module instead of branching on individual tools.
"""
from __future__ import annotations


SUCCESS = "success"
FAILED = "failed"
PARTIAL = "partial"
EMPTY = "empty"
MISSING = "missing"
UNSUPPORTED = "unsupported"
PENDING = "pending"
UNVERIFIED = "unverified"

ALL = (SUCCESS, FAILED, PARTIAL, EMPTY, MISSING, UNSUPPORTED, PENDING, UNVERIFIED)


def _has_partial_signal(data: dict) -> bool:
    """Generic partial-success detector (no tool knowledge).

    Any explicit non-success marker alongside ok=True means partial:
    False flags, "pending"/"failed"/"partial" strings, nonzero failed counts.
    """
    if not isinstance(data, dict):
        return False
    for k, v in data.items():
        lk = str(k).lower()
        if v is False and lk not in ("verified",):
            return True
        if isinstance(v, str) and v.lower() in ("pending", "failed", "partial"):
            return True
        if lk in ("failed", "errors", "failures") and isinstance(v, int) and v > 0:
            return True
    return False


def _has_list_content(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    return any(isinstance(v, list) and len(v) > 0 for v in data.values())


def derive_outcome(tool_result: dict | None, data: dict | None = None) -> str:
    """Map a normalized tool result to a generic outcome.

    tool_result shape: {"ok": bool, "code": str, "error": str}.
    data is the verified payload (may be {}).
    """
    res = tool_result or {}
    data = data if isinstance(data, dict) else {}
    code = str(res.get("code", "")).lower()
    err = str(res.get("error", "")).lower()
    if code in ("approval_pending", "timeout", "pending") or "timed out" in err:
        return PENDING
    if code in ("missing",) or "missing required arguments" in err:
        return MISSING
    if code in ("unsupported", "unknown") or "unknown capability" in err or "unavailable" in err:
        return UNSUPPORTED
    if not res.get("ok"):
        return FAILED
    # ok == True from here.
    if _has_partial_signal(data):
        return PARTIAL
    try:
        from app.ai_assistant import orchestration as _orch
        if _orch.is_proven_result("", data):
            return SUCCESS
    except Exception:
        pass
    if not data or not _has_list_content(data):
        # ok with no content: reads report empty; mutations without proof
        # stay unverified so the AI never claims success.
        if data and any(k in data for k in ("verified", "status", "appointment_id", "id")):
            return UNVERIFIED
        return EMPTY
    if _has_list_content(data):
        return SUCCESS
    return UNVERIFIED


def is_success(outcome: str) -> bool:
    return outcome == SUCCESS


def needs_human_followup(outcome: str) -> bool:
    return outcome in (FAILED, PARTIAL, MISSING, UNVERIFIED, PENDING, EMPTY)
