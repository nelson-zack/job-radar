from __future__ import annotations
import json, re, hashlib
from bs4 import BeautifulSoup
def _soup(html: str) -> BeautifulSoup:
    """
    Parse HTML into a BeautifulSoup object, preferring 'html.parser' but falling back to 'lxml'.
    """
    try:
        return BeautifulSoup(html, "html.parser")
    except Exception:
        return BeautifulSoup(html, "lxml")
from bs4.element import Tag
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

JOB_WORDS = re.compile(r"(apply|responsibilit|qualification|what you'll|what you will|requirements?)", re.I)
JSONLD_TAG = "script"
JSONLD_TYPE = "application/ld+json"
LANDING_PAGE_TITLES = re.compile(r"(careers|search jobs|join us|because impact matters)", re.I)

def _extract_jsonld_jobs(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    for tag in soup.find_all(JSONLD_TAG, type=JSONLD_TYPE):
        # Be defensive: BeautifulSoup can return many element types
        if not isinstance(tag, Tag):
            continue
        raw = tag.string or tag.get_text(strip=False) or ""
        try:
            data = json.loads(raw)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if not isinstance(node, dict):
                continue
            typ = node.get("@type") or node.get("type") or ""
            if isinstance(typ, list):
                is_job = any(isinstance(t, str) and t.lower() == "jobposting" for t in typ)
            else:
                is_job = str(typ).lower() == "jobposting"
            if is_job:
                jobs.append(node)
    return jobs

def is_job_page(html: str, url: str) -> bool:
    soup = _soup(html)
    jobs = _extract_jsonld_jobs(soup)
    if jobs:
        # If JSON-LD jobs found, check title to avoid landing pages
        title = _get_title(soup)
        if LANDING_PAGE_TITLES.search(title):
            return False
        return True

    title = _get_title(soup)
    if LANDING_PAGE_TITLES.search(title):
        return False

    text = soup.get_text(" ", strip=True).lower()
    if not JOB_WORDS.search(text):
        return False

    # Check for "apply" link/button presence
    has_apply_link = False
    for el in soup.find_all(["a", "button"]):
        # Be defensive: BeautifulSoup may return a variety of element types
        if not isinstance(el, Tag):
            continue
        txt = el.get_text(strip=True)
        if txt and "apply" in txt.lower():
            has_apply_link = True
            break

    # Check for known ATS URL patterns
    ats_patterns = ["greenhouse.io", "lever.co", "workday.com", "bamboohr.com", "jobvite.com"]
    parsed_url = urlparse(url)
    has_ats_url = any(domain in parsed_url.netloc for domain in ats_patterns)

    if jobs or (JOB_WORDS.search(text) and (has_apply_link or has_ats_url or "apply" in text)):
        return True

    return False

def _text_or(meta_val) -> Optional[str]:
    if isinstance(meta_val, str):
        return meta_val.strip()
    return None

def _get_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        txt = h1.get_text(strip=True)
        if txt:
            return txt

    mt = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "title"})
    if isinstance(mt, Tag):
        content = mt.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    if soup.title and isinstance(soup.title, Tag) and soup.title.string:
        return str(soup.title.string).strip()
    return ""

def extract_job(html: str, url: str) -> Optional[Dict[str, Any]]:
    soup = _soup(html)

    # 1) JSON-LD first
    jobs = _extract_jsonld_jobs(soup)
    if jobs:
        node = jobs[0]
        org = node.get("hiringOrganization") or {}
        if isinstance(org, dict):
            company = _text_or(org.get("name"))
        else:
            company = _text_or(org) or ""
        title_val = _text_or(node.get("title")) or _get_title(soup)
        if LANDING_PAGE_TITLES.search(title_val):
            return None
        job = {
            "title": title_val,
            "company": company,
            "url": url,
            "description_html": _text_or(node.get("description")) or "",
            "date_posted": _text_or(node.get("datePosted")) or "",
            "location": _text_or(node.get("jobLocationType")) or "",
            "provider": "crawler",
            "source_hash": hashlib.sha1((url + (node.get("title") or "")).encode("utf-8")).hexdigest(),
        }
        return job

    # 2) Heuristic fallback
    title = _get_title(soup)
    if LANDING_PAGE_TITLES.search(title):
        return None
    # Main content guess
    candidates = []
    for sel in ("article", "main", "section", "div"):
        for e in soup.select(sel):
            txt = e.get_text(" ", strip=True)
            if txt and len(txt) > 300 and JOB_WORDS.search(txt):
                candidates.append((len(txt), e))
    candidates.sort(reverse=True, key=lambda t: t[0])
    desc = candidates[0][1].decode_contents() if candidates else ""

    company = urlparse(url).netloc.split(":")[0]
    job = {
        "title": title,
        "company": company,
        "url": url,
        "description_html": desc,
        "date_posted": "",
        "location": "",
        "provider": "crawler",
        "source_hash": hashlib.sha1((url + title).encode("utf-8")).hexdigest(),
    }
    # If we couldn't find any meaningful content, bail
    if not title and not desc:
        return None
    return job