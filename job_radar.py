import argparse
import json
import re
import sys
import csv
from typing import List, Dict
import concurrent.futures
from providers import PROVIDERS
from typing import List
from models import Job
from utils import deduplicate_jobs, load_companies
import os
import requests
from bs4 import BeautifulSoup

JUNIOR_TITLE = re.compile(
    r"\b(junior|new\s*grad|entry\s*level|entry-level|software\s*engineer\s*i\b|associate\b)\b",
    re.IGNORECASE,
)

SENIOR_BLOCK = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head|vp|vice\s*president|chief)\b", re.IGNORECASE)
NON_ENG = re.compile(r"\b(marketing|sales|account\b|account\s*executive|customer\b|success|care|operations|payroll|finance|legal|counsel|attorney|recruit(er|ing)?|designer|architect|solutions|consultant|support|program\s*manager|project\s*manager|product\s*marketing|enablement|coordinator|specialist|analyst)\b", re.IGNORECASE)
MISFIT_TECH = re.compile(r"\b(security|networking|rust)\b", re.IGNORECASE)

ENGINEERING_INCLUDE = re.compile(
    r"\b((software|full[-\s]*stack|fullstack|front[-\s]*end|frontend|back[-\s]*end|backend|platform|web|mobile|ios|android|data|ml|devops)\s*(engineer|developer))\b",
    re.IGNORECASE,
)

REMOTE_US = re.compile(r"\b(remote|fully\s*remote|distributed)\b", re.IGNORECASE)

COUNTRY_BLOCK = re.compile(r"\b(australia|austria|brazil|canada|chile|china|colombia|costa\s*rica|denmark|estonia|finland|france|germany|iceland|india|indonesia|ireland|israel|italy|japan|latvia|lithuania|malaysia|mexico|netherlands|new\s*zealand|norway|philippines|poland|portugal|romania|singapore|south\s*korea|spain|sweden|switzerland|taiwan|thailand|turkey|uae|united\s*arab\s*emirates|united\s*kingdom|uk|england|scotland|wales|ireland|vietnam|berlin|paris|london|toronto|vancouver|montreal|ottawa|amsterdam|madrid|barcelona|reykjavik|warsaw)\b", re.IGNORECASE)
HYBRID_FLAG = re.compile(r"\bhybrid\b", re.IGNORECASE)
REMOTE_FLAG = re.compile(r"\bremote\b", re.IGNORECASE)
US_FLAG = re.compile(r"\b(united\s*states|usa|u\.?s\.?)\b", re.IGNORECASE)

LOCATION_US_REMOTE = re.compile(r"\b(remote)\b.*\b(united\s*states|usa|u\.?s\.?)\b|\b(united\s*states|usa|u\.?s\.?)\b.*\b(remote)\b", re.IGNORECASE)

RELAX_PHRASES = re.compile(r"\b(new\s*grad|recent\s*grad(uate)?|early\s*career|entry\s*level|junior)\b", re.IGNORECASE)

def description_suggests_junior(html: str) -> bool:
    try:
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
    except Exception:
        return False
    if RELAX_PHRASES.search(text):
        return True
    year_hints = [
        "0-1 year", "0-1 years", "0–1 years", "0 to 1 years",
        "0-2 years", "0–2 years", "0 to 2 years",
        "1-2 years", "1–2 years", "1 to 2 years",
        "1-3 years", "1–3 years", "1 to 3 years",
        "2-3 years", "2–3 years", "2 to 3 years",
        "up to 2 years", "less than 3 years", "maximum 2 years"
    ]
    return any(h in text for h in year_hints)

def fetch_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        return r.text
    except Exception:
        return ""

def title_is_eligible(title: str, junior_only: bool, *, block_misfit: bool = True) -> bool:
    t = title.strip()
    # Hard blocks first (cannot be overridden by relax mode)
    if SENIOR_BLOCK.search(t):
        return False
    if NON_ENG.search(t):
        return False
    if block_misfit and MISFIT_TECH.search(t):
        return False
    # Must look like a true engineering role title
    if not ENGINEERING_INCLUDE.search(t):
        return False
    if junior_only:
        # Only true junior signals allowed
        return bool(JUNIOR_TITLE.search(t))
    return True

def looks_remote_us(html: str, location_hint: str, us_only: bool = False, exclude_hybrid: bool = False) -> bool:
    loc = (location_hint or "").strip()

    # Exclude obvious non‑US locations quickly
    if COUNTRY_BLOCK.search(loc):
        return False

    # Exclude hybrids if requested
    if exclude_hybrid and HYBRID_FLAG.search(loc):
        return False

    if us_only:
        # Require explicit US‑remote in the location string to avoid footer noise
        if LOCATION_US_REMOTE.search(loc):
            return True
        # If location is blank/unknown, allow fallback by checking page text
        if not loc:
            if exclude_hybrid and HYBRID_FLAG.search(html):
                return False
            return bool(REMOTE_FLAG.search(html) and US_FLAG.search(html))
        return False

    # Non‑US‑only mode (broader):
    if REMOTE_FLAG.search(loc):
        return True
    if REMOTE_FLAG.search(html):
        return True
    return False

def dedupe(jobs: List[Job]) -> List[Job]:
    seen = set()
    out = []
    for j in jobs:
        key = (j.company.lower(), j.title.lower(), j.url)
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out

def main():
    companies = load_companies()
    tasks = []
    for company in companies:
        provider_key = company.get("provider")
        name = company.get("name")
        token = company.get("token")

        if not provider_key or provider_key not in PROVIDERS:
            print(f"⚠️ Skipping company '{name}' due to missing or unknown provider: {provider_key}")
            continue

        fetch_fn = PROVIDERS[provider_key]
        tasks.append((fetch_fn, name, token))

    all_jobs: List[Job] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(fetch_fn, name, token)
            for fetch_fn, name, token in tasks
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"Error fetching jobs: {e}")

    all_jobs = deduplicate_jobs(all_jobs)

    os.makedirs("output", exist_ok=True)
    with open("output/jobs.json", "w") as f:
        json.dump([job.dict() for job in all_jobs], f, indent=2)

if __name__ == "__main__":
    main()
