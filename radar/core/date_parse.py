from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

MONTHS = {
    'jan': 1,
    'feb': 2,
    'mar': 3,
    'apr': 4,
    'may': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'sep': 9,
    'sept': 9,
    'oct': 10,
    'nov': 11,
    'dec': 12,
}

ISO_DATE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
MONTH_DAY = re.compile(r"^(\w{3,})\s+(\d{1,2})$")
DAYS_AGO = re.compile(r"^(\d+)\s*day[s]?\s*ago$", re.I)
AGE_SHORT = re.compile(r"^(\d+)([dhw])$", re.I)


def parse_curated_date(text: str, *, now: datetime | None = None) -> datetime | None:
    now = now or datetime.utcnow()
    if now.tzinfo:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        now = now.replace(tzinfo=None)

    if not text:
        return None
    raw = text.strip()
    if not raw:
        return None

    m = ISO_DATE.match(raw)
    if m:
        year, month, day = map(int, m.groups())
        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    m = MONTH_DAY.match(raw)
    if m:
        month_name = m.group(1).lower()[:4].strip('. ')
        day = int(m.group(2))
        month = MONTHS.get(month_name[:3])
        if month is None:
            return None
        year = now.year
        try:
            candidate = datetime(year, month, day)
        except ValueError:
            return None
        if candidate - now > timedelta(days=30):
            try:
                candidate = datetime(year - 1, month, day)
            except ValueError:
                return None
        return candidate

    m = DAYS_AGO.match(raw)
    if m:
        days = int(m.group(1))
        return (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    m = AGE_SHORT.match(raw)
    if m:
        value = int(m.group(1))
        unit = m.group(2).lower()
        if unit == 'd':
            return (now - timedelta(days=value)).replace(hour=0, minute=0, second=0, microsecond=0)
        if unit == 'w':
            return (now - timedelta(weeks=value)).replace(hour=0, minute=0, second=0, microsecond=0)
        if unit == 'h':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)

    return None
