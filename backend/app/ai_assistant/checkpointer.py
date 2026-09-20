"""Checkpointer factory: PostgresSaver with MemorySaver fallback.

thread_id == ai_conversations.id. Checkpointer holds ephemeral graph
snapshots only; ai_* tables remain the source of truth.
"""
from __future__ import annotations

import os


def _pg_conn_string() -> str:
    from app.core.config import settings

    url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    return url.replace("postgresql+psycopg2://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")


def get_checkpointer():
    """Return (checkpointer, cleanup). Postgres when available, else memory.

    MemorySaver needs no setup/cleanup. PostgresSaver needs .setup() once
    per database; caller should call setup on first boot.
    """
    use_pg = os.getenv("USE_POSTGRES_CHECKPOINTER", "true").lower() in ("1", "true", "yes")
    if use_pg:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            saver = PostgresSaver.from_conn_string(_pg_conn_string())
            return saver, True
        except Exception:
            pass
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver(), False
