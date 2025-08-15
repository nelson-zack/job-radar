import argparse
import json
import re
import sys
import csv
from typing import List, Dict
from providers import PROVIDERS, Job
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
    ap = argparse.ArgumentParser(description="Remote Junior SWE Radar")
    ap.add_argument("config", help="companies.json path")
    ap.add_argument("--junior-only", action="store_true", help="Only include junior/new grad/SE I titles")
    ap.add_argument("--print-all", action="store_true", help="Print all pulled titles for debugging")
    ap.add_argument("--no-console", action="store_true", help="Do not print matched roles to stdout; write files only")
    ap.add_argument("--out-prefix", default="matches", help="Prefix for output files (e.g., 'matches' writes matches.txt and matches.csv)")
    ap.add_argument("--us-remote-only", action="store_true", help="Only accept roles explicitly Remote in the United States")
    ap.add_argument("--exclude-hybrid", action="store_true", help="Exclude hybrid roles even if remote is mentioned")
    ap.add_argument("--relax-junior", action="store_true", help="Allow roles without explicit junior title if description signals new grad/early career or ≤3 years experience")
    ap.add_argument("--no-misfit-block", action="store_true", help="Do not exclude titles containing Security/Networking/Rust keywords")
    args = ap.parse_args()

    with open(args.config, "r") as f:
        companies = json.load(f)

    all_jobs: List[Job] = []
    for c in companies:
        name = c["company"]
        provider_key = c["ats"]
        fetcher = PROVIDERS.get(provider_key)
        if not fetcher:
            print(f"Skipping {name}: unsupported ATS {provider_key}")
            continue
        try:
            if provider_key == "workday":
                pulled = fetcher(name, c["host"], c["path"])
            else:
                pulled = fetcher(name, c["token"])
        except Exception as e:
            print(f"Error pulling {name}: {e}")
            continue
        all_jobs.extend(pulled)
        if args.print_all:
            print(f"pulled {len(pulled):3d} from {name} ({provider_key})")

    all_jobs = dedupe(all_jobs)

    matches: List[Job] = []
    for j in all_jobs:
        html = fetch_text(j.url)
        if not html:
            continue

        eligible_by_title = title_is_eligible(j.title, args.junior_only, block_misfit=not args.no_misfit_block)
        if not eligible_by_title:
            # In relax mode, still require: not senior, not non‑eng, engineering-looking title
            if args.junior_only and args.relax_junior:
                t = j.title.strip()
                if SENIOR_BLOCK.search(t) or NON_ENG.search(t) or (not ENGINEERING_INCLUDE.search(t)):
                    continue
                if not description_suggests_junior(html):
                    continue
            else:
                continue

        if looks_remote_us(html, j.location, us_only=args.us_remote_only, exclude_hybrid=args.exclude_hybrid):
            matches.append(j)

    if not matches:
        print("No matches found right now.")
        sys.exit(0)

    # Write outputs
    txt_path = f"{args.out_prefix}.txt"
    csv_path = f"{args.out_prefix}.csv"
    with open(txt_path, "w", encoding="utf-8") as ftxt, open(csv_path, "w", newline="", encoding="utf-8") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow(["company", "title", "location", "url"])  # CSV header
        for j in matches:
            ftxt.write(f"{j.company} | {j.title} | {j.location} | {j.url}\n")
            writer.writerow([j.company, j.title, j.location, j.url])

    if not args.no_console:
        print("Matches found:")
        for j in matches:
            print(f"- {j.company} | {j.title} | {j.location} | {j.url}")
    else:
        print(f"Wrote {len(matches)} matches to {txt_path} and {csv_path}")

if __name__ == "__main__":
    main()
