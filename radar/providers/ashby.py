from __future__ import annotations
from typing import Iterable, List
import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from radar.core.normalize import (
    NormalizedJob,
    normalize_title,
    normalize_company,
    canonical_location,
    infer_level,
)

# Per-provider caps (override via RADAR_DESC_CAP_ASHBY, else RADAR_DESC_CAP, else 30)
_DESC_CAP_ENV = os.getenv("RADAR_DESC_CAP_ASHBY") or os.getenv("RADAR_DESC_CAP") or "30"
DESC_CAP = int(_DESC_CAP_ENV)
DESC_TIMEOUT = float(os.getenv("RADAR_DESC_TIMEOUT", "8"))
DESC_MAX_CHARS = int(os.getenv("RADAR_DESC_MAX_CHARS", "1200"))
USER_AGENT = {"User-Agent": "Mozilla/5.0 JobRadar/1.0"}

def _safe_get_json(url: str, timeout: float = 20.0):
    resp = requests.get(url, timeout=timeout, headers=USER_AGENT)
    resp.raise_for_status()
    return resp.json()

def _fetch_text(url: str, timeout: float = DESC_TIMEOUT) -> str:
    try:
        resp = requests.get(url, timeout=timeout, headers=USER_AGENT)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""

def _html_to_snippet(html: str, max_chars: int = DESC_MAX_CHARS) -> str | None:
    if not html:
        return None
    try:
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        text = " ".join(text.split())
        return text[:max_chars] if text else None
    except Exception:
        return None

class AshbyProvider:
    name = "ashby"

    def fetch(self, company: dict) -> Iterable[NormalizedJob]:
        token = company.get("token")
        comp_name = company.get("company", token or "")
        if not token:
            return []

        api_url = f"https://jobs.ashbyhq.com/api/org/{token}/job-postings"
        try:
            data = _safe_get_json(api_url)
        except Exception:
            return []

        jobs: List[NormalizedJob] = []
        desc_count = 0

        # Data is typically a list of postings
        postings = data if isinstance(data, list) else data.get("jobPostings", [])
        for p in postings:
            raw_title = p.get("title", "") or p.get("jobTitle", "")
            title = normalize_title(raw_title)
            if not title:
                continue

            # URL key varies: prefer jobPostingUrl, fall back to jobPostUrl
            url = p.get("jobPostingUrl") or p.get("jobPostUrl") or ""
            if not url:
                # Some APIs nest it differently; last resort use public board URL
                slug = p.get("slug") or ""
                if slug:
                    url = f"https://jobs.ashbyhq.com/{token}/job/{slug}"

            # Location can be plain text like "Remote (US)" — let canonical_location tidy it
            loc = canonical_location(p.get("location", "") or p.get("locationText", "") or "")

            # posted_at: pick the most reliable
            dt_str = p.get("createdAt") or p.get("updatedAt") or ""
            posted_at = None
            if dt_str:
                try:
                    posted_at = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    posted_at = None

            description_snippet = None
            if url and desc_count < DESC_CAP:
                html = _fetch_text(url, timeout=DESC_TIMEOUT)
                snippet = _html_to_snippet(html, max_chars=DESC_MAX_CHARS)
                if snippet:
                    description_snippet = snippet
                    desc_count += 1

            jobs.append(NormalizedJob(
                title=title,
                company=normalize_company(comp_name),
                url=url,
                source=self.name,
                location=loc,
                level=infer_level(title),
                description_snippet=description_snippet,
                posted_at=posted_at,
            ))

        return jobs