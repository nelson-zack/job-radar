from __future__ import annotations

import logging
import os
import re
from typing import Literal, Tuple, Any

LOGGER = logging.getLogger(__name__)

ENTRY_EXCLUSION_TITLE = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|manager|director|head)\b",
    re.IGNORECASE,
)
ENTRY_INCLUSION_TITLE = re.compile(
    r"\b(intern|new\s*grad|junior|entry|associate)\b",
    re.IGNORECASE,
)
PLUS_YEARS_PATTERN = re.compile(r"\b(\d+)\s*\+\s*(?:years?|yrs?)\b", re.IGNORECASE)

EntryDecision = Tuple[Literal['keep', 'exclude'], str]


def is_entry_exclusion_enabled() -> bool:
    return os.getenv("FILTER_ENTRY_EXCLUSIONS", "false").lower() == "true"


def _extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if hasattr(value, "description_snippet"):
        return getattr(value, "description_snippet") or ""
    if hasattr(value, "description"):
        return getattr(value, "description") or ""
    return str(value)


def filter_entry_level(job: Any) -> EntryDecision:
    """Return ('keep'|'exclude', reason) based on title/description heuristics."""
    title = getattr(job, "title", "") if not isinstance(job, dict) else job.get("title", "")
    description = (
        getattr(job, "description", None)
        if not isinstance(job, dict)
        else job.get("description")
    )
    desc_snippet = (
        getattr(job, "description_snippet", None)
        if not isinstance(job, dict)
        else job.get("description_snippet")
    )

    title_text = (title or "").strip()
    desc_text = _extract_text(description) or _extract_text(desc_snippet)

    if not title_text:
        return ("keep", "no-title")

    if ENTRY_EXCLUSION_TITLE.search(title_text):
        return ("exclude", "title-senior-term")

    if desc_text:
        for match in PLUS_YEARS_PATTERN.finditer(desc_text):
            try:
                years = int(match.group(1))
            except ValueError:
                continue
            if years >= 3:
                return ("exclude", "description-3plus-years")

    if ENTRY_INCLUSION_TITLE.search(title_text):
        return ("keep", "title-junior-term")

    return ("keep", "default")


def log_entry_filter_metrics(provider: str, kept: int, excluded: int) -> None:
    LOGGER.info(
        "entry-filter provider=%s flag=%s kept=%s excluded=%s",
        provider,
        is_entry_exclusion_enabled(),
        kept,
        excluded,
    )


def title_exclusion_terms() -> tuple[str, ...]:
    return ("senior", "sr", "staff", "principal", "lead", "manager", "director", "head")


def description_exclusion_patterns() -> tuple[str, ...]:
    patterns = []
    for years in range(3, 16):
        patterns.append(f"%{years}+%year%")
        patterns.append(f"%{years}+%yrs%")
        patterns.append(f"%{years} +%year%")
        patterns.append(f"%{years} +%yrs%")
    return tuple(patterns)
