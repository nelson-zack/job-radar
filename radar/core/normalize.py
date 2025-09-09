from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel

class NormalizedJob(BaseModel):
    title: str
    company: str
    url: str
    source: str
    location: str | None = None
    posted_at: datetime | None = None
    description_snippet: str | None = None
    level: str | None = None
    keywords: list[str] = []

def normalize_title(title: str) -> str:
    return " ".join(title.split()).strip()

def normalize_company(name: str) -> str:
    return " ".join(name.split()).strip()

def canonical_location(loc: str | None) -> str | None:
    if not loc:
        return None
    loc = " ".join(loc.split())
    # Normalize common variants
    loc = loc.replace("United States of America", "United States")
    loc = loc.replace("US-Remote", "Remote - US")
    return loc

def infer_level(title: str, description_html: str | None = None) -> str | None:
    """Infer seniority level from title/description.

    Rules:
      - Explicit junior phrases or I/1 variants → "junior"
      - Explicit senior phrases (Sr/Staff/Principal/Lead/Architect/Manager) → "senior"
      - II/2 variants → "mid" unless the description contains clear junior signals (≤2 years, new grad, etc.)
      - Otherwise None (unknown)
    """
    t = (title or "").lower()
    desc = (description_html or "").lower()

    # --- Junior signals (title or description) ---
    jr_title_phrases = (
        "junior", "new grad", "entry level", "entry-level", "associate",
        "engineer i", "software engineer i", "swe i", "se i", "sde i",
        "level 1", " l1", " l-1", " i)", " i "
    )
    if any(p in t for p in jr_title_phrases):
        return "junior"

    jr_desc_phrases = (
        "junior", "new grad", "recent grad", "entry level", "entry-level",
        "early career", "0-1 years", "0–1 years", "0 to 1 years",
        "0-2 years", "0–2 years", "0 to 2 years", "1-2 years", "1–2 years", "1 to 2 years",
    )
    if any(p in desc for p in jr_desc_phrases):
        return "junior"

    # --- Senior signals ---
    if any(p in t for p in ("senior", "sr.", "sr ", " staff", "principal", "lead", "architect", " manager")):
        return "senior"

    # --- Mid signals (Engineer II / Level 2). Treat as junior only if desc looks junior-ish. ---
    mid_title_phrases = (
        "engineer ii", "software engineer ii", "swe ii", "se ii", "sde ii",
        "level 2", " l2", " l-2", " ii)", " ii "
    )
    if any(p in t for p in mid_title_phrases):
        if any(p in desc for p in jr_desc_phrases):
            return "junior"
        return "mid"

    # Conservative default: unknown
    return None
