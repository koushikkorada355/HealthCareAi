"""Idempotent removal of EHR-integration schema leftovers.

Context: the EHR connector was deleted from the codebase and its columns /
tables were dropped from the SQLAlchemy models. Fresh databases are fine
(create_all simply omits them), but databases created BEFORE the removal
still carry the physical columns as NOT NULL without a server default, so
new inserts that omit them fail (e.g. ai_contexts.integration_state ->
NotNullViolation -> POST /ai/chat 500).

This module drops those leftovers with IF EXISTS DDL: safe to run on every
boot, on fresh and legacy databases, on Postgres and SQLite. Each statement
runs independently; one failure is logged and never blocks boot (same
philosophy as db/exclusion.py).
"""
import logging

logger = logging.getLogger("careaccess")

DROP_COLUMNS = [
    ("hospitals", "ehr_vendor"),
    ("hospitals", "ehr_config"),
    ("hospitals", "external_facility_id"),
    ("doctors", "external_provider_id"),
    ("patients", "external_patient_id"),
    ("appointments", "external_appointment_id"),
    ("appointments", "integration_status"),
    ("ai_contexts", "integration_state"),
]

# Child tables first (FKs reference hospitals/appointments, never the reverse).
DROP_TABLES = [
    "integration_verifications",
    "reconciliation_records",
    "integration_operations",
    "external_id_maps",
    "healthcare_connections",
]


def _existing_columns(engine, table: str) -> set[str]:
    """Column names present right now (empty set if table missing)."""
    try:
        from sqlalchemy import inspect as _inspect
        return {c["name"] for c in _inspect(engine).get_columns(table)}
    except Exception:
        return set()


def ensure_ehr_removed(engine) -> dict:
    """Drop EHR columns/tables left behind by the integration removal.

    Existence-checked (not IF EXISTS) so it works on Postgres and older
    SQLite alike. Returns {"dropped": [...], "skipped": [...]}. Never raises.
    """
    from sqlalchemy import text

    dropped: list[str] = []
    skipped: list[str] = []
    for table, column in DROP_COLUMNS:
        try:
            if column not in _existing_columns(engine, table):
                continue
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
            dropped.append(f"{table}.{column}")
        except Exception as e:
            skipped.append(f"{table}.{column}")
            logger.warning("ehr migration skipped %s.%s: %s", table, column, str(e)[:200])
    for table in DROP_TABLES:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            dropped.append(table)
        except Exception as e:
            skipped.append(table)
            logger.warning("ehr migration skipped table %s: %s", table, str(e)[:200])
    if dropped:
        logger.info("ehr removal migration dropped: %s", ", ".join(dropped))
    return {"dropped": dropped, "skipped": skipped}
