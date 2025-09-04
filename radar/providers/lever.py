from __future__ import annotations
from typing import Iterable, List
import requests

from radar.core.normalize import NormalizedJob, normalize_title, normalize_company, canonical_location, infer_level

def _safe_get(url: str, **kwargs) -> requests.Response:
    resp = requests.get(url, timeout=kwargs.get("timeout", 20))
    resp.raise_for_status()
    return resp

class LeverProvider:
    name = "lever"

    def fetch(self, company: dict) -> Iterable[NormalizedJob]:
        token = company.get("token")
        comp_name = company.get("company", token or "")
        if not token:
            return []

        api_url = f"https://api.lever.co/v0/postings/{token}?mode=json"
        try:
            data = _safe_get(api_url).json()
        except Exception:
            return []

        jobs: List[NormalizedJob] = []
        for j in data:
            url = j.get("hostedUrl") or j.get("applyUrl") or ""
            title = normalize_title(j.get("text", ""))
            loc = None
            if j.get("categories") and j["categories"].get("location"):
                loc = canonical_location(j["categories"]["location"])
            jobs.append(NormalizedJob(
                title=title,
                company=normalize_company(comp_name),
                url=url,
                source=self.name,
                location=loc,
                level=infer_level(title),
                description_snippet=None,
            ))
        return jobs
