"""Pydantic schemas for the AI Assistant Layer.

Schemas are data contracts only — they enforce no policy. All enforcement
lives in nodes/safety.py + nodes/tool_router.py.
"""
from typing import Any, Literal
from pydantic import BaseModel, Field


Category = Literal["administrative", "clinical", "unrelated", "ambiguous", "unsupported"]


class Classification(BaseModel):
    """Structured understanding of one user turn."""

    category: Category = "ambiguous"
    # Intent reuses the platform vocabulary (extends app/ai intent set).
    intent: str = "unknown"
    entities: dict[str, Any] = Field(default_factory=dict)
    # specialty, doctor_name, city, date_pref, slot_iso, appointment_id, ...
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_action_write: bool = False
    # True when the turn may cause a state-changing tool call
    # (create/reschedule/cancel/submit) — forces the confirm loop.


class SafetyVerdict(BaseModel):
    """Outcome of the safety layer for one turn."""

    verdict: Literal["allow", "deny", "escalate"] = "allow"
    reason_category: str = ""
    # clinical|urgent|injection|out_of_scope|policy — never raw user text.
    detail: str = ""
    # Short operator-safe note; never echoes sensitive content.


class PendingConfirmation(BaseModel):
    """A state-changing tool call awaiting explicit user confirmation."""

    tool: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = ""
    summary: str = ""
    # Human-readable echo-back shown to the user (doctor/slot/time).


class ToolCall(BaseModel):
    """A validated, gated tool invocation ready for the MCP adapter."""

    name: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = ""
    tool_call_id: str = ""


class AgentResponse(BaseModel):
    """Channel-independent structured assistant response."""

    reply: str = ""
    trace: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    powered_by: str = "rules"
    graph_run_id: str = ""
    safety: dict[str, str] = Field(default_factory=dict)
