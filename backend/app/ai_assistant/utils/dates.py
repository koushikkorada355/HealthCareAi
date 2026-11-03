"""Global date normalization: LLM-first, deterministic ISO fallback.

No hardcoded month/weekday/relative-day word lists. The LLM extracts
{date_iso, days, day_part} in any language (see CLASSIFY_SYSTEM). This module
only validates ISO output and parses explicit ISO datetimes so the router
always passes concrete args to check_availability.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _coerce_days(v) -> int:
    if v in (None, "", 0, "0", False):
        return 0
    try:
        from app.core.config import settings
        cap = int(getattr(settings, "AI_MAX_DAYS", 14))
    except Exception:
        cap = 14
    try:
        return max(1, min(int(v), cap))
    except (TypeError, ValueError):
        return 0


def normalize(text: str, now: datetime | None = None) -> dict:
    """Sync fallback: parse explicit ISO dates only (no language rules).

    Full natural-language understanding lives in the LLM classifier
    (date_iso/days/time_window). This keeps calendar truth deterministic
    without English regex lists. Existing callers pass classification dates
    via `normalize_global`.
    """
    now = now or datetime.now(timezone.utc)
    t = (text or "").strip()
    if not t:
        return {}
    out: dict = {}
    # Explicit ISO date only — universal format, no language words.
    import re as _re

    m = _re.search(r"(\d{4}-\d{2}-\d{2})", t)
    if m:
        try:
            datetime.fromisoformat(m.group(1))
            out["date_iso"] = m.group(1)
            out.setdefault("days", 1)
        except ValueError:
            pass
    return out


def normalize_global(classification: dict | None, tx: dict | None = None,
                     now: datetime | None = None) -> dict:
    """Build router-ready {date_iso, days, day_part} from LLM entities.

    Pure data plumbing — no language regex. Prefers explicit date_iso,
    clamps days to 1-14, passes through the universal day_part bucket.
    """
    cls = classification or {}
    tx = tx or {}
    out: dict = {}
    date_iso = str(cls.get("date_iso") or tx.get("date_iso") or "").strip()[:10]
    if date_iso:
        try:
            datetime.fromisoformat(date_iso)
            out["date_iso"] = date_iso
        except ValueError:
            pass
    days = _coerce_days(cls.get("days") or tx.get("days") or 0)
    if days:
        out["days"] = days
    elif date_iso:
        out["days"] = 1
    part = str(cls.get("time_window") or tx.get("time_window") or "").lower().strip()
    if part in ("morning", "afternoon", "evening"):
        out["day_part"] = part
    # Explicit hour window from the LLM wins over named buckets (global).
    for src in (cls, tx):
        tr = (src or {}).get("time_range")
        if isinstance(tr, dict):
            try:
                out["time_range"] = {"start_hr": int(tr["start_hr"]), "end_hr": int(tr["end_hr"])}
                break
            except (KeyError, TypeError, ValueError):
                continue
    # Back-compat: older classify shape carried raw "dates" text that may
    # contain an ISO date; harvest it without language lists.
    if "date_iso" not in out and cls.get("dates"):
        iso = normalize(str(cls.get("dates")), now=now)
        out.update(iso)
    return out
