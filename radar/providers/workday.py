from __future__ import annotations
from typing import Iterable, List
import requests
import os
from bs4 import BeautifulSoup

# Description fetching caps (can be overridden via environment variables)
DESC_CAP = int(os.getenv("RADAR_DESC_CAP", "30"))           # max descriptions to fetch per provider
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
        text = " ".join(text.split())
        if not text:
            return None
        return text[:max_chars]
    except Exception:
        return None

from radar.core.normalize import NormalizedJob, normalize_title, normalize_company, canonical_location, infer_level

def _safe_get(url: str, **kwargs) -> requests.Response:
    resp = requests.get(url, timeout=kwargs.get("timeout", 20))
    resp.raise_for_status()
    return resp

class WorkdayProvider:
    name = "workday"

    def fetch(self, company: dict) -> Iterable[NormalizedJob]:
        host = company.get("host")
        path = company.get("path", "External")
        comp_name = company.get("company", host or "")
        if not host:
            return []

        api_url = f"https://{host}/wday/cxs/{host}/{path}/jobs"
        try:
            data = _safe_get(api_url, timeout=25).json()
        except Exception:
            return []

        jobs: List[NormalizedJob] = []
        desc_count = 0
        for j in data.get("jobPostings", []):
            url = f"https://{host}/en-US/careers/job/{j.get('bulletFields', [''])[0]}" if j.get("bulletFields") else f"https://{host}"
            title = normalize_title(j.get("title", ""))
            loc = canonical_location(j.get("locationsText"))
            description_snippet = None
            if url and desc_count < DESC_CAP:
                html = _fetch_text(url, timeout=DESC_TIMEOUT)
                snippet = _html_to_snippet(html, max_chars=DESC_MAX_CHARS)
                if snippet:
                    description_snippet = snippet
                    desc_count += 1
            # --- posted_at extraction (Workday) ---
            posted_at = None
            # Workday payloads vary; try common keys and a nested meta field
            candidates = [
                j.get("postedOn"),
                j.get("postedDate"),
                j.get("startDate"),
                j.get("datePosted"),
                (j.get("meta") or {}).get("postedDate"),
            ]
            for val in candidates:
                if not val:
                    continue
                try:
                    from datetime import datetime, timezone
                    # Try ISO8601 first
                    posted_at = datetime.fromisoformat(str(val).replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                    break
                except Exception:
                    try:
                        # Try epoch seconds or milliseconds
                        ts = float(val)
                        if ts > 1e12:  # milliseconds
                            ts = ts / 1000.0
                        posted_at = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
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
