from __future__ import annotations
from typing import Iterable, List
import requests

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
        for j in data.get("jobPostings", []):
            url = f"https://{host}/en-US/careers/job/{j.get('bulletFields', [''])[0]}" if j.get("bulletFields") else f"https://{host}"
            title = normalize_title(j.get("title", ""))
            loc = canonical_location(j.get("locationsText"))
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
