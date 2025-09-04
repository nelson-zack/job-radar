from __future__ import annotations
import re
import yaml
from typing import Any

# --- Title & category guards ---
ENGINEERING_HINTS = re.compile(r"\\b(software|frontend|back[- ]?end|full[- ]?stack|platform|web|mobile|data|ml|devops|sre|site reliability)\\b", re.I)
SENIOR_BLOCK = re.compile(r"\\b(senior|staff|principal|lead|manager|architect)\\b", re.I)
JUNIOR_POSITIVE = re.compile(r"\\b(junior|new grad|entry level|software engineer i|associate)\\b", re.I)

def looks_like_engineering(title: str) -> bool:
    return bool(ENGINEERING_HINTS.search(title))

def is_junior_title_or_desc(title: str, description_html: str | None, relaxed: bool = False) -> bool:
    title_l = title.lower()
    if SENIOR_BLOCK.search(title_l):
        return False
    if JUNIOR_POSITIVE.search(title_l):
        return True
    if not relaxed:
        return False
    # Relaxed: allow signals in description (very light-weight placeholder; improve later)
    if not description_html:
        return False
    return any(k in description_html.lower() for k in ("new grad", "early career", "0-3 years", "0–3 years", "<=3 years"))

def looks_remote_us(location: str | None, description_html: str | None) -> bool:
    if location:
        loc = location.lower()
        if "remote" in loc and ("united states" in loc or "us" in loc):
            return True
    # Fallback to page description
    if description_html:
        text = description_html.lower()
        return ("remote" in text) and ("united states" in text or "us" in text)
    return False

# --- YAML rules loader (for Phase 2) ---
def load_rules_file(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data
