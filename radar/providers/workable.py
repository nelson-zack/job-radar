from __future__ import annotations
from typing import Iterable, List
import os
import requests
import re
from bs4 import BeautifulSoup
from bs4.element import Tag
from radar.core.normalize import (
    NormalizedJob, normalize_title, normalize_company,
    canonical_location, infer_level
)

_DESC_CAP_ENV = os.getenv("RADAR_DESC_CAP_WORKABLE") or os.getenv("RADAR_DESC_CAP") or "30"
DESC_CAP = int(_DESC_CAP_ENV)
DESC_TIMEOUT = float(os.getenv("RADAR_DESC_TIMEOUT", "8"))
DESC_MAX_CHARS = int(os.getenv("RADAR_DESC_MAX_CHARS", "1200"))
UA = {"User-Agent": "Mozilla/5.0 JobRadar/1.0"}

def _get(url: str, timeout: float = 20.0) -> requests.Response:
    resp = requests.get(url, headers=UA, timeout=timeout)
    resp.raise_for_status()
    return resp

def _fetch_text(url: str, timeout: float = DESC_TIMEOUT) -> str:
    try:
        return _get(url, timeout=timeout).text
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

class WorkableProvider:
    name = "workable"

    def fetch(self, company: dict) -> Iterable[NormalizedJob]:
        token = company.get("token")
        comp_name = company.get("company", token or "")
        if not token:
            return []

        # Try apply.workable.com/<token>/ first, then <token>.workable.com
        candidates = [
            f"https://apply.workable.com/{token}/",
            f"https://{token}.workable.com/",
        ]

        html, base_used = "", ""
        for base in candidates:
            html = _fetch_text(base)
            if html:
                base_used = base.rstrip("/")
                break
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        jobs: List[NormalizedJob] = []
        desc_count = 0

        # Link patterns on apply.workable.com are usually '/<token>/j/<slug>/'
        # On <token>.workable.com they are '/jobs/<slug>'
        anchors = soup.find_all("a", href=True)
        for a in anchors:
            if not isinstance(a, Tag):
                continue
            raw_href = a.get("href")
            if isinstance(raw_href, list):
                href = str(raw_href[0]).strip()
            else:
                href = (str(raw_href) if raw_href is not None else "").strip()

            if not href:
                continue

            is_apply = f"/{token}/j/" in href or href.startswith("/j/")
            is_subdom = "/jobs/" in href

            if not (is_apply or is_subdom):
                continue

            url = href if href.startswith("http") else f"{base_used}{href}"

            raw_title = a.get_text(" ", strip=True)
            title = normalize_title(raw_title)
            if not title:
                continue

            # Location: look around the link
            loc = None
            parent = a.find_parent()
            if isinstance(parent, Tag):
                loc_el = parent.find(class_="location")
                if not loc_el:
                    # try another common pattern (case-insensitive)
                    loc_el = parent.find("span", string=re.compile(r"\bremote\b", re.I))
                if isinstance(loc_el, Tag):
                    loc = canonical_location(loc_el.get_text(" ", strip=True))

            description_snippet = None
            if url and desc_count < DESC_CAP:
                jhtml = _fetch_text(url, timeout=DESC_TIMEOUT)
                snippet = _html_to_snippet(jhtml, max_chars=DESC_MAX_CHARS)
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
                posted_at=None,  # Workable dates are not consistent in markup
            ))

        return jobs