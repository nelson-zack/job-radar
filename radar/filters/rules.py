from __future__ import annotations
import re
import yaml
from typing import Any
from datetime import datetime, timedelta, timezone

# --- Engineering title heuristics (broadened, with false-positive guards) ---
CORE_SWE_HINTS = re.compile(
    r"\b(software|full[- ]?stack|fullstack|front[- ]?end|frontend|back[- ]?end|backend|platform|web|mobile|ios|android|data|ml|machine\s*learning|devops|sre|site\s*reliability|security|infrastructure)\b",
    re.I,
)
GENERIC_ENGINEER = re.compile(r"\b(engineer|developer)\b", re.I)
# Exclude common non-SWE variants unless paired with core SWE hints
NON_SWE_ENGINEER = re.compile(
    r"\b(sales|account|customer|support|success|implementation|solutions|field|pre[- ]?sales|professional\s*services)\s+(engineer|engineering)\b",
    re.I,
)
SENIOR_BLOCK = re.compile(r"\b(senior|staff|principal|lead|manager|architect|sr\b)\b", re.I)
JUNIOR_POSITIVE = re.compile(r"\b(junior|new\s*grad|entry\s*level|entry-level|software\s*engineer\s*i|associate)\b", re.I)
YEARS_0_TO_3 = re.compile(r"\b(0[-–]?[123]|1[-–]?2|1[-–]?3|2[-–]?3)\s*(\+\s*)?(years|yrs)\b", re.I)


def looks_like_engineering(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    # Block obvious non-SWE engineer variants unless accompanied by core hints
    if NON_SWE_ENGINEER.search(t) and not CORE_SWE_HINTS.search(t):
        return False
    # Positive matches: core SWE hints or generic engineer/developer
    if CORE_SWE_HINTS.search(t):
        return True
    if GENERIC_ENGINEER.search(t):
        return True
    return False


def is_junior_title_or_desc(title: str, description_html: str | None, relaxed: bool = False) -> bool:
    t = (title or "")
    if SENIOR_BLOCK.search(t):
        return False
    if JUNIOR_POSITIVE.search(t):
        return True
    if YEARS_0_TO_3.search(t):
        return True
    if not relaxed or not description_html:
        return False
    text = description_html.lower()
    return any(k in text for k in (
        "new grad", "recent grad", "early career", "entry level",
        "0-1 years", "0–1 years", "0 to 1 years",
        "0-2 years", "0–2 years", "0 to 2 years",
        "1-2 years", "1–2 years", "1 to 2 years",
        "1-3 years", "1–3 years", "1 to 3 years",
    ))


def looks_remote_us(location: str | None, description_html: str | None) -> bool:
    if location:
        loc = location.lower()
        if (
            "remote" in loc and (
                "united states" in loc or "u.s." in loc or "usa" in loc or loc.endswith(" us") or " us " in loc
            )
        ):
            return True
    if description_html:
        text = description_html.lower()
        return ("remote" in text) and ("united states" in text or "u.s." in text or "usa" in text)
    return False


def is_recent(posted_at: datetime | None, days: int = 7) -> bool:
    """Return True if `posted_at` is within the last `days` days (UTC).
    Expects a naive UTC datetime (providers normalize to naive).
    """
    if not posted_at:
        return False
    try:
        now = datetime.now(timezone.utc)
        # If posted_at is naive, assume it's UTC; otherwise compare directly
        if posted_at.tzinfo is None:
            return (now.replace(tzinfo=None) - posted_at) <= timedelta(days=days)
        return (now - posted_at) <= timedelta(days=days)
    except Exception:
        return False


# --- YAML rules loader (Phase 2 support) ---
def load_rules_file(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data
