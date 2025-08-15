# providers.py
from __future__ import annotations
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional
import time

# Real UA helps avoid some blocks
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

@dataclass
class Job:
    company: str
    title: str
    url: str
    location: str
    source: str

def _safe_get(url: str, timeout: int = 20) -> Optional[requests.Response]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None

# ---------- Greenhouse via public API ----------
def fetch_greenhouse(company_name: str, board_token: str) -> List[Job]:
    """
    Example: https://boards-api.greenhouse.io/v1/boards/vercel/jobs?content=true
    """
    api = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    r = _safe_get(api)
    if not r:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    jobs: List[Job] = []
    for j in data.get("jobs", []):
        title = (j.get("title") or "").strip()
        url = j.get("absolute_url") or ""
        loc = ((j.get("location") or {}).get("name") or "").strip()
        if title and url:
            jobs.append(Job(company_name, title, url, loc, "greenhouse"))
    return jobs

# ---------- Lever via public API ----------
def fetch_lever(company_name: str, board_token: str) -> List[Job]:
    """
    Example: https://api.lever.co/v0/postings/snyk?mode=json
    """
    api = f"https://api.lever.co/v0/postings/{board_token}?mode=json"
    r = _safe_get(api)
    if not r:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    jobs: List[Job] = []
    for p in data:
        title = (p.get("text") or p.get("title") or "").strip()
        url = p.get("hostedUrl") or p.get("applyUrl") or p.get("url") or ""
        categories = p.get("categories") or {}
        location = (categories.get("location") or "").strip()
        if title and url:
            jobs.append(Job(company_name, title, url, location, "lever"))
    return jobs

# ---------- Ashby (HTML parse; no public JSON) ----------
def fetch_ashby(company_name: str, slug: str) -> List[Job]:
    """
    Example: https://jobs.ashbyhq.com/notion
    """
    url = f"https://jobs.ashbyhq.com/{slug}"
    r = _safe_get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    jobs: List[Job] = []
    for a in soup.select(f"a[href^='/{slug}/']"):
        href_attr = a.get("href")
        # Coerce href to a plain string
        if isinstance(href_attr, list):
            href = href_attr[0] if href_attr else ""
        else:
            href = href_attr or ""
        href = str(href).strip()

        title = a.get_text(" ", strip=True)
        if not href or not title or len(title.split()) < 2:
            continue

        job_url = href if href.startswith("http") else f"https://jobs.ashbyhq.com{href}"

        # Try to find a nearby location snippet
        location = ""
        parent = a.find_parent()
        if parent:
            text = parent.get_text(" ", strip=True)
            if "Remote" in text or "United States" in text or "US" in text:
                location = text

        jobs.append(Job(company_name, title, job_url, location, "ashby"))
    return jobs

# ---------- Workday via JSON ----------
def fetch_workday(company_name: str, host: str, path: str) -> List[Job]:
    """
    Example: https://directv.wd1.myworkdayjobs.com/wday/cxs/directv/External/jobs
    """
    api = f"https://{host}/wday/cxs/{host}/{path}/jobs"
    r = _safe_get(api, timeout=25)
    if not r:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    jobs: List[Job] = []
    for jp in data.get("jobPostings", []):
        title = (jp.get("title") or "").strip()
        ext = jp.get("externalPath")
        if not title or not ext:
            continue
        url = f"https://{host}/{ext.lstrip('/')}"
        loc = ""
        if jp.get("locations"):
            loc = ", ".join(jp.get("locations") or [])
        elif jp.get("location"):
            loc = (jp["location"].get("name") or "").strip()
        jobs.append(Job(company_name, title, url, loc, "workday"))
        time.sleep(0.1)
    return jobs

PROVIDERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
}