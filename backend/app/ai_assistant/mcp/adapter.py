"""MCP adapter: schema validation + routing. Contracts live in registry.

No per-tool tables here: required args and types are read dynamically from
``registry.TOOL_SCHEMAS`` so a new tool needs zero changes in this file.
``REQUIRED_ARGS`` / ``INT_ARGS`` remain as deprecated read-only views for
existing callers/tests.
"""
from __future__ import annotations


class _CompatMap(dict):
    def __init__(self, kind: str):
        self._kind = kind

    def _live(self) -> dict:
        from app.ai_assistant.mcp import registry as reg
        out = {}
        for t in reg.tool_names():
            schema = reg.get_schema(t)
            out[t] = list(schema.get("required" if self._kind == "required" else "int_args", []))
        return out

    def get(self, k, d=None):
        return self._live().get(k, d if d is not None else [])

    def __getitem__(self, k):
        return self._live()[k]

    def __contains__(self, k):
        return k in self._live()


REQUIRED_ARGS: dict[str, list[str]] = _CompatMap("required")  # type: ignore[assignment]
INT_ARGS: dict[str, list[str]] = _CompatMap("int")  # type: ignore[assignment]


def known_tools() -> list[str]:
    from app.ai_assistant.mcp import registry as reg

    return reg.tool_names()


def validate(name: str, args: dict | None) -> tuple[dict, str]:
    from app.ai_assistant.mcp import registry as reg

    if name not in reg._IMPL:
        return {}, f"Unknown capability {name}."
    schema = reg.get_schema(name)
    args = dict(args or {})
    missing = [k for k in schema.get("required", []) if args.get(k) in (None, "")]
    if missing:
        return {}, f"Missing required arguments: {', '.join(missing)}."
    coerced = dict(args)
    for k in schema.get("int_args", []):
        if coerced.get(k) in (None, ""):
            continue
        try:
            coerced[k] = int(coerced[k])
        except (TypeError, ValueError):
            return {}, f"Argument {k} must be an integer."
    return coerced, ""


async def call(db, name: str, args: dict | None, *, user, conversation_id=None,
               idempotency_key: str = "", corr: str = "",
               tool_call_id: str = "", timeout_s: float | None = None) -> dict:
    from app.ai_assistant.mcp import client as mcp_client
    from app.ai_assistant import orchestration as orch

    coerced, error = validate(name, args)
    if error:
        return {"ok": False, "code": "invalid", "error": error,
                "latency_ms": 0, "tool_call_id": tool_call_id}
    if timeout_s is None:
        timeout_s = orch.timeout_for(name)
    out = await mcp_client.invoke(
        db, name, coerced, user=user, conversation_id=conversation_id,
        idempotency_key=idempotency_key, corr=corr or "", timeout_s=timeout_s)
    out["tool_call_id"] = tool_call_id or mcp_client.new_tool_call_id()
    return out
