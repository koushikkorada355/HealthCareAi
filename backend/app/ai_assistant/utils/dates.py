"""Deterministic date/window normalization (calendar truth, not LLM wording).

Converts relative day references to ISO dates and day-part windows so the
router always passes concrete args to check_availability.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}
_MONTHS.update({m[:3]: i for m, i in _MONTHS.items()})

_DAY_PARTS = {
    "morning": "morning", "mornings": "morning", "am": "morning",
    "afternoon": "afternoon", "afternoons": "afternoon", "afternon": "afternoon",
    "evening": "evening", "evenings": "evening", "night": "evening", "pm": "evening",
}

_WEEKDAYS = {d: i for i, d in enumerate(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}


def normalize(text: str, now: datetime | None = None) -> dict:
    """Return {date_iso, days, day_part}. Empty dict when nothing found."""
    now = now or datetime.now(timezone.utc)
    t = (text or "").lower()
    out: dict = {}
    for k, v in _DAY_PARTS.items():
        if re.search(rf"\b{re.escape(k)}\b", t):
            out["day_part"] = v
            break
    if re.search(r"\btoday\b", t):
        out["date_iso"] = now.date().isoformat()
        out.setdefault("days", 1)
        return out
    if re.search(r"\btomm?orrow\b", t):
        out["date_iso"] = (now + timedelta(days=1)).date().isoformat()
        out.setdefault("days", 1)
        return out
    m = re.search(r"\b(this week|this coming week)\b", t)
    if m:
        out.setdefault("days", 7)
        return out
    m = re.search(r"\bnext week\b", t)
    if m:
        out["date_iso"] = (now + timedelta(days=7 - now.weekday())).date().isoformat()
        out.setdefault("days", 7)
        return out
    m = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b", t)
    if m:
        day, month = int(m.group(1)), _MONTHS[m.group(2)[:3]]
        year = now.year
        try:
            cand = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return out
        if cand.date() < now.date():
            cand = datetime(year + 1, month, day, tzinfo=timezone.utc)
        out["date_iso"] = cand.date().isoformat()
        out.setdefault("days", 1)
        return out
    m = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
    if m:
        month, day = _MONTHS[m.group(1)[:3]], int(m.group(2))
        year = now.year
        try:
            cand = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            return out
        if cand.date() < now.date():
            cand = datetime(year + 1, month, day, tzinfo=timezone.utc)
        out["date_iso"] = cand.date().isoformat()
        out.setdefault("days", 1)
        return out
    for name, wd in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", t):
            delta = (wd - now.weekday()) % 7
            if delta == 0 and re.search(r"\bnext\b", t):
                delta = 7
            out["date_iso"] = (now + timedelta(days=delta)).date().isoformat()
            out.setdefault("days", 1)
            return out
    return out
