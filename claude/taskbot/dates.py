"""Small natural-language date parser.

Deliberately dependency-free and deliberately narrow. It handles the
shapes people actually text — "friday", "tomorrow", "aug 20", "8/20" —
and returns None for anything else so the caller can treat the text as
part of the task title instead.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse(text: str, today: date | None = None) -> date | None:
    """Parse a due date from a short phrase.

    Args:
        text: Something like "friday", "next tuesday", "8/20", "aug 20".
        today: Reference date, injectable for tests. Defaults to today.

    Returns:
        The resolved date, or None if nothing recognizable was found.
    """
    if not text:
        return None
    today = today or date.today()
    s = text.strip().lower().rstrip(".,!?")
    s = re.sub(r"^(by|on|due|before)\s+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return None

    if s == "today":
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    if s in ("tonight", "this evening"):
        return today

    # "next friday" / "this friday" / bare "friday"
    m = re.fullmatch(r"(?:(next|this)\s+)?(\w+)", s)
    if m and m.group(2) in WEEKDAYS:
        qualifier, name = m.group(1), m.group(2)
        ahead = (WEEKDAYS[name] - today.weekday()) % 7
        if ahead == 0:
            # "friday" said on a Friday means the next one, not today.
            ahead = 7
        if qualifier == "next":
            # "next friday" is the one after the upcoming friday.
            ahead += 7
        return today + timedelta(days=ahead)

    # "in 3 days" / "in 2 weeks"
    m = re.fullmatch(r"in (\d+) (day|days|week|weeks)", s)
    if m:
        n = int(m.group(1))
        return today + timedelta(days=n * (7 if m.group(2).startswith("week") else 1))

    # "aug 20" / "august 20th" / "20 aug"
    m = re.fullmatch(r"([a-z]+)\.? (\d{1,2})(?:st|nd|rd|th)?", s)
    if m and m.group(1) in MONTHS:
        return _resolve(MONTHS[m.group(1)], int(m.group(2)), today)
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)? ([a-z]+)\.?", s)
    if m and m.group(2) in MONTHS:
        return _resolve(MONTHS[m.group(2)], int(m.group(1)), today)

    # "8/20" or "8/20/26" or "2026-08-20"
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", s)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if m.group(3):
            year = int(m.group(3))
            if year < 100:
                year += 2000
            return _safe_date(year, month, day)
        return _resolve(month, day, today)

    return None


def _resolve(month: int, day: int, today: date) -> date | None:
    """Pick the year for a month/day with no year given.

    Always resolves forward: a date that already passed this year means
    next year.
    """
    candidate = _safe_date(today.year, month, day)
    if candidate is None:
        return None
    if candidate < today:
        return _safe_date(today.year + 1, month, day)
    return candidate


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
