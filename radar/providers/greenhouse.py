from __future__ import annotations
from typing import Iterable, List
import os, json, re
import requests
from bs4 import BeautifulSoup

import logging

from radar.core.normalize import NormalizedJob, normalize_title, normalize_company, canonical_location, infer_level
from radar.filters.rules import JUNIOR_POSITIVE, SENIOR_BLOCK, looks_like_engineering
from radar.filters.entry import (
    filter_entry_level,
    is_entry_exclusion_enabled,
    log_entry_filter_metrics,
)

# Description fetching caps (can be overridden via environment variables)
# Per-provider cap: prefer RADAR_DESC_CAP_GREENHOUSE, else fallback to RADAR_DESC_CAP
_DESC_CAP_ENV = os.getenv("RADAR_DESC_CAP_GREENHOUSE") or os.getenv("RADAR_DESC_CAP") or "30"
DESC_CAP = int(_DESC_CAP_ENV)
DESC_TIMEOUT = float(os.getenv("RADAR_DESC_TIMEOUT", "8"))  # seconds per HTTP request
DESC_MAX_CHARS = int(os.getenv("RADAR_DESC_MAX_CHARS", "1200"))

# Extra ranking hints for snippet prefetch prioritization
JUNIOR_TITLE_BONUS = re.compile(
    r"\b(new\s*grad|junior|associate|engineer\s*[i1]\b|software\s*engineer\s*[i1]\b|swe\s*[i1]\b|sde\s*[i1]\b|level\s*1\b|l1\b|university|graduate|grad)\b",
    re.I,
)
ML_DS = re.compile(r"\b(data\s*scientist|machine\s*learning|ml)\b", re.I)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) JobRadar/1.0 Chrome/123 Safari/537.36",
      "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.8"}

def _fetch_text(url: str, timeout: float = DESC_TIMEOUT) -> str:
    try:
        resp = requests.get(url, timeout=timeout, headers=UA)
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
    resp = requests.get(url, timeout=kwargs.get("timeout", 20), headers=UA)
    resp.raise_for_status()
    return resp


def _parse_date_from_jsonld(html: str) -> str | None:
    """Return ISO-ish date string from a JobPosting JSON-LD block, if present."""
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("script", type="application/ld+json"):
            raw = getattr(tag, "string", None)
            if raw is None:
                raw = tag.get_text(strip=False) if hasattr(tag, "get_text") else ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            blocks = data if isinstance(data, list) else [data]
            for b in blocks:
                if isinstance(b, dict) and b.get("@type") in ("JobPosting", "Posting"):
                    dt = b.get("datePosted") or b.get("datePublished") or b.get("dateCreated")
                    if isinstance(dt, str) and dt.strip():
                        return dt.strip()
    except Exception:
        return None
    return None

class GreenhouseProvider:
    name = "greenhouse"
    _logger = logging.getLogger(__name__)

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
        kept_counter = 0
        excluded_counter = 0
        entry_filter_enabled = is_entry_exclusion_enabled()
        debug_entry = os.getenv("RADAR_DEBUG_ENTRY_FILTER", "0") == "1"
        desc_count = 0
        # Sort & group to spend snippet budget on junior-leaning SWE roles first
        raw_jobs = list(data.get("jobs", []))

        def _priority_key(jobj: dict) -> tuple[int, int, int, int, int]:
            t = normalize_title(jobj.get("title", ""))
            t_l = t.lower()
            # Junior hit if core junior regex OR extra junior-title bonuses match
            junior_hit = 1 if (JUNIOR_POSITIVE.search(t_l) or JUNIOR_TITLE_BONUS.search(t_l)) else 0
            senior_hit = 1 if SENIOR_BLOCK.search(t_l) else 0
            eng_hit   = 1 if looks_like_engineering(t_l) else 0
            # Mild downrank for ML/Data Scientist *unless* junior-ish
            ml_penalty = 1 if (ML_DS.search(t_l) and not junior_hit) else 0
            # Higher priority sorts first by NEGATED keys. Order:
            # 1) junior-ish SWE first
            # 2) non-ML/DS (unless junior) slightly ahead
            # 3) non-senior ahead of senior
            # 4) engineering-ish ahead of generic
            # 5) shorter titles first as tiny tie-breaker
            return (-junior_hit, ml_penalty, senior_hit, -eng_hit, len(t_l))

        # Two-phase ordering:
        #   1) junior-ish SWE titles (non-senior) sorted by key
        #   2) everything else sorted by key
        jr_first: list[dict] = []
        rest: list[dict] = []
        for jobj in raw_jobs:
            t_l = normalize_title(jobj.get("title", "")).lower()
            is_juniorish = bool(JUNIOR_POSITIVE.search(t_l) or JUNIOR_TITLE_BONUS.search(t_l))
            if is_juniorish and not SENIOR_BLOCK.search(t_l) and looks_like_engineering(t_l):
                jr_first.append(jobj)
            else:
                rest.append(jobj)
        jr_first.sort(key=_priority_key)
        rest.sort(key=_priority_key)
        ordered_jobs = jr_first + rest

        jr_prefetch_count = 0
        for j in ordered_jobs:
            url = j.get("absolute_url") or ""
            title = normalize_title(j.get("title", ""))
            loc = None
            if j.get("location") and j["location"].get("name"):
                loc = canonical_location(j["location"]["name"])

            description_snippet = None
            html = None
            if url and desc_count < DESC_CAP:
                html = _fetch_text(url, timeout=DESC_TIMEOUT)
                snippet = _html_to_snippet(html, max_chars=DESC_MAX_CHARS)
                if snippet:
                    description_snippet = snippet
                    desc_count += 1
                    # track if this snippet went to a junior-leaning SWE title
                    tl = title.lower()
                    if JUNIOR_POSITIVE.search(tl) and looks_like_engineering(tl) and not SENIOR_BLOCK.search(tl):
                        jr_prefetch_count += 1

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
            if posted_at is None and html:
                iso = _parse_date_from_jsonld(html)
                if iso:
                    try:
                        from datetime import datetime
                        posted_at = datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        posted_at = None

            job = NormalizedJob(
                title=title,
                company=normalize_company(comp_name),
                url=url,
                source=self.name,
                location=loc,
                level=infer_level(title),
                description_snippet=description_snippet,
                posted_at=posted_at,
            )

            decision, reason = filter_entry_level({
                "title": job.title,
                "description": description_snippet,
            })
            if entry_filter_enabled and decision == "exclude":
                excluded_counter += 1
                if debug_entry:
                    self._logger.debug(
                        "entry-filter exclude provider=%s title=%s reason=%s url=%s",
                        self.name,
                        job.title,
                        reason,
                        job.url,
                    )
                continue

            kept_counter += 1
            jobs.append(job)
        if os.getenv("RADAR_DEBUG_GREENHOUSE"):
            try:
                print(f"[greenhouse] snippet fetch: total={desc_count} cap={DESC_CAP} junior_prefetch={jr_prefetch_count}")
            except Exception:
                pass
        if entry_filter_enabled:
            log_entry_filter_metrics(self.name, kept_counter, excluded_counter)
        return jobs
