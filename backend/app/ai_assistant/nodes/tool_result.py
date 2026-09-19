"""Tool result node: executes selected tools via the MCP adapter.

- Reads (`selected`): invoke immediately, record normalized outcome.
- Writes (`confirmed` only): invoke with the pending idempotency key, then
  consume the pending confirmation (single execution — a second identical
  confirm finds empty pending and asks instead of re-running).
- Outcomes recorded verbatim: {ok, code, data|error}. Response rendering
  never claims more than the recorded outcome.
"""
from __future__ import annotations

from ..mcp import adapter, client


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    db, user = rt.get("db"), rt.get("user")
    trace = list(state.get("trace", []))
    tool = state.get("selected_tool", "")
    status = state.get("tool_status", "skipped")

    if not tool or status not in ("selected", "confirmed"):
        return {"tool_result": {"ok": True, "code": "skipped", "data": {}},
                "trace": [*trace, f"result: {status or 'skipped'}"]}

    pending = state.get("pending_confirmation") or {}
    idem = pending.get("idempotency_key", "") if status == "confirmed" else ""
    out = await adapter.call(
        db, tool, dict(state.get("tool_args") or {}), user=user,
        conversation_id=state.get("conversation_id") or rt.get("conversation_id"),
        idempotency_key=idem, corr=rt.get("corr", ""),
        tool_call_id=client.new_tool_call_id(),
    )
    update: dict = {
        "tool_result": out,
        "tool_status": "ok" if out.get("ok") else out.get("code", "failed"),
        "trace": [*trace, f"result: {tool} -> {out.get('code')}"],
    }
    if status == "confirmed":
        update["pending_confirmation"] = {}  # consumed: exactly-once confirm
    return update
