from __future__ import annotations
from typing import Iterable, List, Any
import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from bs4.element import Tag
from radar.core.normalize import (
    NormalizedJob,
    normalize_title,
    normalize_company,
    canonical_location,
    infer_level,
)
import re
import json
from urllib.parse import urljoin

# Per-provider caps (override via RADAR_DESC_CAP_ASHBY, else RADAR_DESC_CAP, else 30)
_DESC_CAP_ENV = os.getenv("RADAR_DESC_CAP_ASHBY") or os.getenv("RADAR_DESC_CAP") or "30"
DESC_CAP = int(_DESC_CAP_ENV)
DESC_TIMEOUT = float(os.getenv("RADAR_DESC_TIMEOUT", "8"))
DESC_MAX_CHARS = int(os.getenv("RADAR_DESC_MAX_CHARS", "1200"))
USER_AGENT = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) JobRadar/1.0 Chrome/123 Safari/537.36", "Accept": "text/html,application/json;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.8"}

RADAR_DEBUG_ASHBY = os.getenv("RADAR_DEBUG_ASHBY", "0") == "1"
def _dbg(msg: str) -> None:
    if RADAR_DEBUG_ASHBY:
        print(f"[ashby] {msg}")

def _guess_slugs(token: str, html: str | None = None) -> list[str]:
    candidates = [token]
    if '.' in token:
        candidates.append(token.replace('.', '-'))
        candidates.append(token.replace('.', ''))
        candidates.append(token.split('.', 1)[0])
    if html:
        # organizationSlug":"([a-z0-9-\.]+)"
        for m in re.finditer(r'"organizationSlug"\s*:\s*"([a-z0-9\-\.]+)"', html, re.I):
            slug = m.group(1)
            if slug not in candidates:
                candidates.append(slug)
        # \bslug\":\"([a-z0-9-\.]+)\" within "organization":{...}
        for org_block in re.finditer(r'"organization"\s*:\s*\{.*?\}', html, re.S):
            block = org_block.group(0)
            for m in re.finditer(r'\bslug"\s*:\s*"([a-z0-9\-\.]+)"', block, re.I):
                slug = m.group(1)
                if slug not in candidates:
                    candidates.append(slug)
        # data-organization-slug=\"([^\"]+)\"
        for m in re.finditer(r'data-organization-slug="([^"]+)"', html):
            slug = m.group(1)
            if slug not in candidates:
                candidates.append(slug)
    # Deduplicate preserving order
    seen = set()
    result = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result

def _safe_get_json(url: str, timeout: float = 20.0, referer: str | None = None):
    headers = USER_AGENT.copy()
    if referer is not None:
        headers["Referer"] = referer
    resp = requests.get(url, timeout=timeout, headers=headers)
    resp.raise_for_status()
    return resp.json()

def _safe_post_json(url: str, payload: dict[str, Any], timeout: float = 20.0, referer: str | None = None):
    headers = USER_AGENT.copy()
    headers["Content-Type"] = "application/json"
    if referer is not None:
        headers["Referer"] = referer
    resp = requests.post(url, json=payload, timeout=timeout, headers=headers)
    resp.raise_for_status()
    return resp.json()

def _graphql_list(slug: str, referer: str | None = None) -> list[dict]:
    graphql_url = "https://jobs.ashbyhq.com/api/graphql"
    queries = [
        {
            "query": """
            query JobsByOrg($organizationSlug: String!) {
              organization(slug: $organizationSlug) {
                jobPostings {
                  nodes {
                    title
                    jobPostingUrl
                    locationText
                    publishedAt
                    updatedAt
                  }
                }
              }
            }
            """,
            "variables": {"organizationSlug": slug},
        },
        {
            "query": """
            query JobPostingsByOrg($organizationSlug: String!) {
              jobPostingsByOrganizationSlug(slug: $organizationSlug) {
                nodes {
                  title
                  jobPostUrl
                  locationText
                  publishedAt
                  updatedAt
                }
              }
            }
            """,
            "variables": {"organizationSlug": slug},
        },
    ]

    results: list[dict] = []

    def _walk(obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from _walk(v)
        elif isinstance(obj, list):
            for it in obj:
                yield from _walk(it)

    for q in queries:
        try:
            resp_json = _safe_post_json(graphql_url, q, timeout=20.0, referer=referer)
            for node in _walk(resp_json):
                if not isinstance(node, dict):
                    continue
                u = node.get("jobPostingUrl") or node.get("jobPostUrl") or node.get("url") or node.get("jobUrl")
                if isinstance(u, str) and f"/{slug}/" in u:
                    abs_url = u if u.startswith(("http://", "https://")) else urljoin("https://jobs.ashbyhq.com/", u)
                    slug_val = abs_url.rstrip("/").split("/")[-1]
                    title = node.get("title") or node.get("jobTitle") or ""
                    locationText = node.get("locationText")
                    publishedAt = node.get("publishedAt")
                    updatedAt = node.get("updatedAt")
                    entry = {"title": title, "jobPostingUrl": abs_url, "slug": slug_val}
                    if locationText:
                        entry["locationText"] = locationText
                    if publishedAt:
                        entry["publishedAt"] = publishedAt
                    if updatedAt:
                        entry["updatedAt"] = updatedAt
                    results.append(entry)
        except Exception:
            continue

    return results

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

def _fallback_list(token: str) -> list[dict]:
    index_url = f"https://jobs.ashbyhq.com/{token}"
    html = _fetch_text(index_url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")

    seen: dict[str, dict] = {}

    # --- Strategy -1: scan raw HTML for JSON-embedded jobPostingUrl with escaped slashes ---
    try:
        esc_token = re.escape(token).replace('/', r'\/')
        pat_json_url = re.compile(
            rf'"jobPostingUrl"\s*:\s*"(?P<u>(?:\\/)?{esc_token}(?:\\/job\\/[^"\\\s<>]+|\\/[a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}}))"'
        )
        for m in pat_json_url.finditer(html):
            u = m.group('u').replace('\\/', '/')
            abs_url = u if u.startswith(('http://','https://')) else urljoin('https://jobs.ashbyhq.com/', u.lstrip('/'))
            slug = abs_url.rstrip('/').split('/')[-1]
            if abs_url not in seen:
                seen[abs_url] = {"title": "", "jobPostingUrl": abs_url, "slug": slug}
    except Exception:
        pass

    # --- Strategy 0: Next.js __NEXT_DATA__ JSON (some Ashby boards embed jobs here) ---
    try:
        script = soup.find("script", id="__NEXT_DATA__")
        script_text = script.get_text(strip=False) if script else None
        if script_text:
            next_data = json.loads(script_text)

            def _walk(obj):
                if isinstance(obj, dict):
                    yield obj
                    for v in obj.values():
                        yield from _walk(v)
                elif isinstance(obj, list):
                    for it in obj:
                        yield from _walk(it)

            for node in _walk(next_data):
                u = None
                if isinstance(node, dict):
                    u = node.get("jobPostingUrl") or node.get("jobPostUrl") or node.get("url") or node.get("jobUrl")
                if isinstance(u, str) and f"/{token}/" in u:
                    abs_url = u if u.startswith(("http://", "https://")) else urljoin("https://jobs.ashbyhq.com/", u)
                    title = ""
                    if isinstance(node, dict):
                        title = node.get("title") or node.get("jobTitle") or ""
                    slug = abs_url.rstrip("/").split("/")[-1]
                    seen[abs_url] = {"title": title, "jobPostingUrl": abs_url, "slug": slug}
    except Exception:
        pass

    # --- Strategy 0.5: parse any <script> JSON blobs and walk for posting URLs ---
    try:
        def _try_json(txt: str):
            try:
                return json.loads(txt)
            except Exception:
                return None

        def _walk_any(obj):
            if isinstance(obj, dict):
                yield obj
                for v in obj.values():
                    yield from _walk_any(v)
            elif isinstance(obj, list):
                for it in obj:
                    yield from _walk_any(it)

        for sc in soup.find_all("script"):
            sc_txt = sc.get_text(strip=False) or ""
            if not sc_txt:
                continue
            # quick filter to avoid huge non-JSON blobs
            if '"' not in sc_txt and '{' not in sc_txt:
                continue
            js = _try_json(sc_txt)
            if js is None:
                continue
            for node in _walk_any(js):
                if not isinstance(node, dict):
                    continue
                u = node.get("jobPostingUrl") or node.get("jobPostUrl") or node.get("url") or node.get("jobUrl")
                if isinstance(u, str) and f"/{token}/" in u:
                    abs_url = u if u.startswith(("http://", "https://")) else urljoin("https://jobs.ashbyhq.com/", u)
                    title = node.get("title") or node.get("jobTitle") or ""
                    slug = abs_url.rstrip("/").split("/")[-1]
                    if abs_url not in seen:
                        seen[abs_url] = {"title": title, "jobPostingUrl": abs_url, "slug": slug}
    except Exception:
        pass

    pat_job = re.compile(rf"/{re.escape(token)}/job/([^/?#]+)")
    pat_uuid = re.compile(rf"/{re.escape(token)}/([a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}})")

    # --- Strategy A: parse <a href=...> elements ---
    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag):
            continue
        href_val = a.get("href")
        if not isinstance(href_val, str):
            continue
        href = href_val.strip()
        m = pat_job.search(href) or pat_uuid.search(href)
        if not m:
            continue
        abs_url = href if href.startswith(("http://", "https://")) else urljoin("https://jobs.ashbyhq.com/", href)
        title = a.get_text(" ", strip=True) or a.get("aria-label") or a.get("title") or ""
        seen[abs_url] = {"title": title, "jobPostingUrl": abs_url, "slug": m.group(1)}

    # --- Strategy B: raw regex on HTML (helps if anchors are nested/obfuscated) ---
    for m in re.finditer(rf"(?:href=)?\"?(/?{re.escape(token)}/(?:job/[^\"'?#\s<>]+|[a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}}))\"?", html):
        href = m.group(1)
        abs_url = href if href.startswith(("http://", "https://")) else urljoin("https://jobs.ashbyhq.com/", href)
        if abs_url in seen:
            continue
        seen[abs_url] = {"title": "", "jobPostingUrl": abs_url, "slug": m.group(1).split("/")[-1]}

    # --- Strategy C: generic JSON-string URL scan (no key name requirements) ---
    try:
        esc_token = re.escape(token).replace('/', r'\/')
        pat_any_url = re.compile(rf'"(?P<u>\/?{esc_token}\/(?:job\/[^"\\\s<>]+|[a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}}))"')
        for m in pat_any_url.finditer(html):
            u = m.group('u').replace('\\/', '/')
            abs_url = u if u.startswith(('http://','https://')) else urljoin('https://jobs.ashbyhq.com/', u.lstrip('/'))
            slug = abs_url.rstrip('/').split('/')[-1]
            if abs_url not in seen:
                seen[abs_url] = {"title": "", "jobPostingUrl": abs_url, "slug": slug}
    except Exception:
        pass

    jobs = list(seen.values())
    _dbg(f"fallback results for {token}: {len(jobs)}")
    return jobs

class AshbyProvider:
    name = "ashby"

    def fetch(self, company: dict) -> Iterable[NormalizedJob]:
        token = company.get("token")
        comp_name = company.get("company", token or "")
        if not token:
            return []

        index_url = f"https://jobs.ashbyhq.com/{token}"
        html_for_guess = _fetch_text(index_url)
        slugs = _guess_slugs(token, html_for_guess)
        _dbg(f"slugs: {slugs}")

        postings: list = []
        for slug in slugs:
            api_url = f"https://jobs.ashbyhq.com/api/org/{slug}/job-postings"
            try:
                data = _safe_get_json(api_url, referer=index_url)
                if isinstance(data, list) and data:
                    postings = data
                    break
                elif isinstance(data, dict) and (data.get("jobPostings") or data.get("jobs")):
                    postings = data.get("jobPostings", []) or data.get("jobs", [])
                    if postings:
                        break
            except Exception:
                continue

        _dbg(f"json results: {len(postings)}")

        if not postings:
            for slug in slugs:
                try:
                    postings = _graphql_list(slug, referer=index_url)
                    if postings:
                        break
                except Exception:
                    continue
        _dbg(f"graphql results: {len(postings)}")

        if not postings:
            postings = _fallback_list(token)
        _dbg(f"final/fallback results: {len(postings)}")

        jobs: List[NormalizedJob] = []
        desc_count = 0

        # Data is typically a list of postings
        for p in postings:
            raw_title = p.get("title", "") or p.get("jobTitle", "")
            title = normalize_title(raw_title)
            if not title:
                continue

            # URL key varies: prefer jobPostingUrl, fall back to jobPostUrl, url, jobUrl
            url = p.get("jobPostingUrl") or p.get("jobPostUrl") or p.get("url") or p.get("jobUrl") or ""
            if not url:
                # Some APIs nest it differently; last resort use public board URL
                slug_val = p.get("slug") or ""
                if slug_val:
                    url = f"https://jobs.ashbyhq.com/{token}/job/{slug_val}"

            # Location can be plain text like "Remote (US)" — let canonical_location tidy it
            loc = canonical_location(p.get("location", "") or p.get("locationText", "") or "")

            # posted_at: pick the most reliable
            dt_str = (
                p.get("createdAt")
                or p.get("publishedAt")
                or p.get("updatedAt")
                or p.get("liveAt")
                or p.get("posting", {}).get("publishedAt")
                or p.get("posting", {}).get("updatedAt")
                or ""
            )
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