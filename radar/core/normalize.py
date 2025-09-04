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
    t = title.lower()
    if any(k in t for k in ("junior", "new grad", "entry level", "software engineer i", "associate")) :
        return "junior"
    return None
