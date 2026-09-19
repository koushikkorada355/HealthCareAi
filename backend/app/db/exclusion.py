"""Postgres exclusion constraint for overlapping bookings (Option A).

Blocks any overlapping tstzrange for the same doctor while the appointment
is in an active state. Exact-start duplicates were already blocked by
uq_doctor_slot; this closes the overlapping-range race
(e.g. 10:00-10:30 vs 10:15-10:45).

Neon-safe: pure DDL, no session locks, works with PgBouncer transaction mode.
SQLite-safe: skipped unless engine dialect is postgresql, so unit tests keep passing.

One-time rollout on existing DBs (Neon/local pgdata):
  1. Run find_overlaps() — must return 0 rows, else reschedule/cancel them.
  2. ensure_exclusion() runs CREATE EXTENSION + ALTER TABLE (idempotent).
Fresh DBs get it automatically via lifespan after create_all.
"""
import logging

logger = logging.getLogger("careaccess")

CONSTRAINT_NAME = "excl_doctor_no_overlap"

ACTIVE_STATUSES = (
    "pending",
    "confirmed",
    "sync_pending",
    "rescheduled",
    "reconciliation_required",
)

CREATE_EXTENSION_SQL = "CREATE EXTENSION IF NOT EXISTS btree_gist;"

CONSTRAINT_EXISTS_SQL = (
    "SELECT 1 FROM pg_constraint WHERE conname = :name AND conrelid = "
    "'appointments'::regclass"
)

ADD_CONSTRAINT_SQL = f"""
ALTER TABLE appointments
ADD CONSTRAINT {CONSTRAINT_NAME}
EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(starts_at, ends_at) WITH &&
)
WHERE (status IN ('pending', 'confirmed', 'sync_pending', 'rescheduled', 'reconciliation_required'));
"""

FIND_OVERLAPS_SQL = """
SELECT a1.id AS id1, a2.id AS id2, a1.doctor_id,
       a1.starts_at, a1.ends_at
FROM appointments a1
JOIN appointments a2
  ON a1.doctor_id = a2.doctor_id
 AND a1.id < a2.id
 AND tstzrange(a1.starts_at, a1.ends_at) && tstzrange(a2.starts_at, a2.ends_at)
WHERE a1.status IN ('pending', 'confirmed', 'sync_pending', 'rescheduled', 'reconciliation_required')
  AND a2.status IN ('pending', 'confirmed', 'sync_pending', 'rescheduled', 'reconciliation_required')
LIMIT 50;
"""


def _is_postgres(engine) -> bool:
    try:
        return engine.dialect.name == "postgresql"
    except Exception:
        return False


def find_overlaps(engine) -> list:
    """Return up to 50 overlapping active pairs (empty = safe to migrate)."""
    if not _is_postgres(engine):
        return []
    from sqlalchemy import text

    with engine.connect() as conn:
        rows = conn.execute(text(FIND_OVERLAPS_SQL)).fetchall()
    return [dict(r._mapping) for r in rows]


def ensure_exclusion(engine) -> dict:
    """Idempotent: extension + exclusion constraint. Never raises (logs instead).

    Returns {"skipped": reason} | {"created": bool, "overlaps": [...]}.
    Safe to call on every boot (lifespan) and on SQLite (skipped).
    """
    if not _is_postgres(engine):
        return {"skipped": "non-postgres dialect"}
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            conn.execute(text(CREATE_EXTENSION_SQL))
    except Exception as e:
        logger.warning("btree_gist extension failed (continuing): %s", e)
        return {"skipped": f"extension failed: {e}"}

    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text(CONSTRAINT_EXISTS_SQL), {"name": CONSTRAINT_NAME}
            ).first()
        if exists:
            return {"created": False, "overlaps": []}
    except Exception as e:
        logger.warning("constraint check failed (continuing): %s", e)
        return {"skipped": f"check failed: {e}"}

    overlaps = find_overlaps(engine)
    if overlaps:
        logger.warning(
            "exclusion constraint NOT created: %d overlapping active appointments "
            "exist; reschedule/cancel them then restart",
            len(overlaps),
        )
        return {"created": False, "overlaps": overlaps}

    try:
        with engine.begin() as conn:
            conn.execute(text(ADD_CONSTRAINT_SQL))
        logger.info("created exclusion constraint %s", CONSTRAINT_NAME)
        return {"created": True, "overlaps": []}
    except Exception as e:
        msg = str(e)
        # Concurrent boot / already exists race — treat as success.
        if "already exists" in msg or CONSTRAINT_NAME in msg:
            logger.info("exclusion constraint already present (race): %s", msg[:200])
            return {"created": False, "overlaps": []}
        logger.warning("exclusion constraint failed (continuing): %s", msg[:500])
        return {"skipped": f"alter failed: {msg[:300]}"}
