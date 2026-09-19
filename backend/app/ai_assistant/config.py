"""AI Assistant Layer configuration (env-driven, no secrets in code).

All values come from process env / .env with safe defaults so the layer
runs fully offline (deterministic fallback) when no LLM key is present.
"""
import os


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# Cutover flag: "1" serves POST /ai/chat through this layer (old path = fallback).
AI_ASSISTANT_V2 = _get("AI_ASSISTANT_V2", "1").lower() in ("1", "true", "yes")

# LLM wiring (provider-independent; Grok-compatible OpenAI client underneath).
LLM_TIMEOUT_S = _get_float("AI_LLM_TIMEOUT_S", 15.0)
LLM_CLASSIFY_MAX_TOKENS = _get_int("AI_LLM_CLASSIFY_MAX_TOKENS", 300)
LLM_CLASSIFY_TEMPERATURE = _get_float("AI_LLM_CLASSIFY_TEMPERATURE", 0.0)
LLM_PROVIDER = _get("AI_LLM_PROVIDER", "grok")

# Conversation handling.
HISTORY_WINDOW = _get_int("AI_HISTORY_WINDOW", 10)
SUMMARY_THRESHOLD = _get_int("AI_SUMMARY_THRESHOLD", 20)

# MCP adapter.
MCP_TIMEOUT_S = _get_float("AI_MCP_TIMEOUT_S", 15.0)
