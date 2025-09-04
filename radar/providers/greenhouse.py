from __future__ import annotations
from typing import Iterable, List
import requests

from radar.core.normalize import NormalizedJob, normalize_title, normalize_company, canonical_location, infer_level

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
        for j in data.get("jobs", []):
            url = j.get("absolute_url") or ""
            title = normalize_title(j.get("title", ""))
            loc = None
            if j.get("location") and j["location"].get("name"):
                loc = canonical_location(j["location"]["name"])
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
