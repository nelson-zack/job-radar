from __future__ import annotations
from typing import Iterable, List
import os
import requests
from bs4 import BeautifulSoup

from radar.core.normalize import NormalizedJob, normalize_title, normalize_company, canonical_location, infer_level

# Description fetching caps (can be overridden via environment variables)
# Per-provider cap: prefer RADAR_DESC_CAP_GREENHOUSE, else fallback to RADAR_DESC_CAP
_DESC_CAP_ENV = os.getenv("RADAR_DESC_CAP_GREENHOUSE") or os.getenv("RADAR_DESC_CAP") or "30"
DESC_CAP = int(_DESC_CAP_ENV)
DESC_TIMEOUT = float(os.getenv("RADAR_DESC_TIMEOUT", "8"))  # seconds per HTTP request
DESC_MAX_CHARS = int(os.getenv("RADAR_DESC_MAX_CHARS", "1200"))

def _fetch_text(url: str, timeout: float = DESC_TIMEOUT) -> str:
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 JobRadar/1.0"})
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""

def _html_to_snippet(html: str, max_chars: int = DESC_MAX_CHARS) -> str | None:
    if not html:
        return None
    try:
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        # collapse whitespace
        text = " ".join(text.split())
        if not text:
            return None
        return text[:max_chars]
    except Exception:
        return None

def _safe_get(url: str, **kwargs) -> requests.Response:
    resp = requests.get(url, timeout=kwargs.get("timeout", 20))
    resp.raise_for_status()
    return resp

class GreenhouseProvider:
    name = "greenhouse"

    def fetch(self, company: dict) -> Iterable[NormalizedJob]:
        """Fetch jobs for a Greenhouse company.

        Expected company entry example:
        {"provider": "greenhouse", "token": "vercel", "company": "Vercel"}
        """
        token = company.get("token")
        comp_name = company.get("company", token or "")
        if not token:
            return []

        api_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        try:
            data = _safe_get(api_url).json()
        except Exception:
            return []

        jobs: List[NormalizedJob] = []
        desc_count = 0
        for j in data.get("jobs", []):
            url = j.get("absolute_url") or ""
            title = normalize_title(j.get("title", ""))
            loc = None
            if j.get("location") and j["location"].get("name"):
                loc = canonical_location(j["location"]["name"])

            description_snippet = None
            if url and desc_count < DESC_CAP:
                html = _fetch_text(url, timeout=DESC_TIMEOUT)
                snippet = _html_to_snippet(html, max_chars=DESC_MAX_CHARS)
                if snippet:
                    description_snippet = snippet
                    desc_count += 1

            # --- posted_at extraction (Greenhouse) ---
            posted_at = None
            for key in ("updated_at", "created_at", "opened_at", "internal_job_updated_at"):
                val = j.get(key)
                if val:
                    try:
                        from datetime import datetime
                        posted_at = datetime.fromisoformat(str(val).replace("Z", "+00:00")).replace(tzinfo=None)
                        break
                    except Exception:
                        posted_at = None

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
