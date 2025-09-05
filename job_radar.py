import argparse
import json
from datetime import datetime, timezone

# --- JSON helpers ---
def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)

# stdlib
import re
import sys
import csv
from typing import List, Dict
from pathlib import Path
import concurrent.futures
# NEW: use modular Radar package
from radar.providers import REGISTRY as PROVIDER_REGISTRY
from radar.core.normalize import NormalizedJob
from radar.core.dedupe import deduplicate_jobs as dedupe_normalized
from radar.filters.rules import (
    looks_like_engineering,
    is_junior_title_or_desc,
    looks_remote_us as rules_looks_remote_us,
    is_recent,
)
from utils import load_companies
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

def legacy_looks_remote_us(html: str, location_hint: str, us_only: bool = False, exclude_hybrid: bool = False) -> bool:
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

def dedupe(jobs):
    """Backward-compatible wrapper; prefers normalized dedupe if objects are NormalizedJob."""
    try:
        return dedupe_normalized(jobs)  # works for NormalizedJob
    except Exception:
        # Fallback: legacy tuple-based dedupe
        seen = set()
        out = []
        for j in jobs:
            key = (str(getattr(j, "company", "")).lower(), str(getattr(j, "title", "")).lower(), getattr(j, "url", ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(j)
        return out

def _matches_basic(job: NormalizedJob, *, junior_only: bool = False, relax: bool = True, us_remote_only: bool = False) -> bool:
    # If we're in fully relaxed mode (no junior/us constraints), accept anything with a non-empty title.
    if not junior_only and not us_remote_only:
        return bool(job.title and job.title.strip())

    # 1) Must look like engineering
    if not looks_like_engineering(job.title):
        return False

    # 2) Junior-only: treat anything NOT explicitly senior/staff/lead as acceptable
    if junior_only:
        title_l = job.title.lower()
        senior_markers = ("senior", "staff", "principal", "lead", "manager", "architect", "sr ")
        if any(s in title_l for s in senior_markers):
            return False
        # if explicit junior, always pass
        if is_junior_title_or_desc(job.title, job.description_snippet, relaxed=relax):
            return True
        # neutral (no senior keywords) passes too
        return True

    # 3) US-remote-only: if location missing, don't block; if present, apply a light check
    if us_remote_only:
        loc = (job.location or "").lower()
        if loc and ("remote" not in loc or ("united states" not in loc and "us" not in loc)):
            return False

    return True

#
# --- default skills loader ---
def _load_default_skills(path_arg: str | None = None):
    """Load default skills from a JSON file.
    The file may define keys: {"any": [...], "all": [...]} or {"skills_any": [...], "skills_all": [...]}.
    Search order:
      1) explicit --skills-defaults path (if provided)
      2) $RADAR_DEFAULT_SKILLS env var
      3) config/default_skills.json (repo default)
    Returns (skills_any_list, skills_all_list) or ([], []) if not found/invalid.
    """
    # Determine path
    if path_arg:
        p = Path(path_arg)
    else:
        env_p = os.getenv("RADAR_DEFAULT_SKILLS")
        p = Path(env_p) if env_p else Path("config/default_skills.json")

    try:
        if not p.exists():
            return [], []
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        any_list = data.get("any") or data.get("skills_any") or []
        all_list = data.get("all") or data.get("skills_all") or []
        # Normalize: strings -> list (comma-separated) if needed
        if isinstance(any_list, str):
            any_list = [s.strip() for s in any_list.split(",") if s.strip()]
        if isinstance(all_list, str):
            all_list = [s.strip() for s in all_list.split(",") if s.strip()]
        # Lowercase
        any_list = [str(s).strip().lower() for s in any_list if str(s).strip()]
        all_list = [str(s).strip().lower() for s in all_list if str(s).strip()]
        return any_list, all_list
    except Exception:
        return [], []

# --- begin: provider/company field normalization helpers ---
def _normalize_company_entry(raw: dict) -> dict:
    # Accept common aliases so companies.json is flexible
    provider = (raw.get("provider") or raw.get("source") or raw.get("ats") or "").strip().lower() or None
    company = raw.get("company") or raw.get("name") or raw.get("org") or None
    token = raw.get("token") or raw.get("board_token") or None
    host = raw.get("host") or raw.get("domain") or None
    path = raw.get("path") or raw.get("environment") or "External"
    return {
        "provider": provider,
        "company": company,
        "token": token,
        "host": host,
        "path": path,
        "priority": raw.get("priority"),
    }

def _debug_companies_preview(items, n=3):
    print("— companies.json preview —")
    for i, c in enumerate(items[:n]):
        print(f"  [{i}] keys={list(c.keys())} provider={c.get('provider') or c.get('source') or c.get('ats')} company={c.get('company') or c.get('name')}")
    print("— end preview —")
# --- end: helpers ---

def main():
    parser = argparse.ArgumentParser(description="Job Radar")
    parser.add_argument("companies_file", type=str, nargs="?", default="companies.json", help="Path to companies.json file")
    parser.add_argument("--relax", action="store_true", help="Relax filtering rules")
    parser.add_argument("--no-summary", action="store_true", help="Suppress fetched/kept/unique counts and preview output")
    parser.add_argument("--junior-only", action="store_true", help="Filter to junior/entry-level roles only")
    parser.add_argument("--us-remote-only", action="store_true", help="Require roles to be remote within the United States")
    parser.add_argument("--recent-days", type=int, default=0,
                        help="Only keep roles posted within the last N days (0 disables)")
    parser.add_argument("--require-date", action="store_true",
                        help="When using --recent-days, drop roles that don't provide posted_at")

    # Description snippet controls (override provider env defaults)
    parser.add_argument("--desc-cap", type=int, default=None, help="Max descriptions to fetch per provider (overrides RADAR_DESC_CAP)")
    parser.add_argument("--desc-timeout", type=float, default=None, help="Seconds timeout per description fetch (overrides RADAR_DESC_TIMEOUT)")
    parser.add_argument("--desc-max-chars", type=int, default=None, help="Max characters to keep in description snippet (overrides RADAR_DESC_MAX_CHARS)")

    # Skills filters
    parser.add_argument("--skills-any", type=str, default="", help="Comma-separated list; keep if ANY term appears in title or description")
    parser.add_argument("--skills-all", type=str, default="", help="Comma-separated list; keep only if ALL terms appear in title or description")
    parser.add_argument("--skills-hard", action="store_true",
                        help="Treat skills filters as hard gates (drop roles with no matches). By default they are soft: used for ranking only.")
    parser.add_argument("--skills-defaults", type=str, default=None,
                        help="Path to a JSON file with default skills {any: [...], all: [...]} used when --skills-any/all are not provided")

    # CSV export
    parser.add_argument("--min-score", type=int, default=0,
                        help="Drop roles with skill_score below this value (applies after scoring; default 0)")
    parser.add_argument("--csv-out", type=str, default="output/jobs.csv",
                        help="Path to write a CSV export of the kept results (default: output/jobs.csv)")

    args = parser.parse_args()

    # Apply CLI overrides for provider snippet fetching (providers read env vars)
    if args.desc_cap is not None:
        os.environ["RADAR_DESC_CAP"] = str(args.desc_cap)
    if args.desc_timeout is not None:
        os.environ["RADAR_DESC_TIMEOUT"] = str(args.desc_timeout)
    if args.desc_max_chars is not None:
        os.environ["RADAR_DESC_MAX_CHARS"] = str(args.desc_max_chars)

    # Show available providers in the registry (helps diagnose mismatches)
    if not args.no_summary:
        print("Available providers:", ", ".join(sorted(PROVIDER_REGISTRY.keys())) or "(none)")

    companies_raw = load_companies(args.companies_file)
    if not isinstance(companies_raw, list):
        try:
            companies_raw = list(companies_raw)
        except Exception:
            companies_raw = []

    # Preview a few entries to reveal key names present in companies.json
    if not args.no_summary:
        _debug_companies_preview(companies_raw, n=3)

    companies = [_normalize_company_entry(c) for c in companies_raw]

    # Map company name -> priority for attaching to outputs
    priority_by_company: Dict[str, str] = {}
    for c in companies:
        name = (c.get("company") or "").strip()
        if name:
            pr = c.get("priority")
            if pr is not None:
                priority_by_company[name.lower()] = str(pr)

    tasks = []
    for company in companies:
        provider_key = company.get("provider")
        if not provider_key or provider_key not in PROVIDER_REGISTRY:
            print(f"⚠️ Skipping company '{company.get('company')}' due to missing or unknown provider: {provider_key}")
            continue

        provider = PROVIDER_REGISTRY[provider_key]
        # Pass the normalized company payload straight to the provider
        tasks.append((provider, company))

    all_jobs: List[NormalizedJob] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(provider.fetch, company_payload)
            for provider, company_payload in tasks
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"Error fetching jobs: {e}")

    # --- Description snippet diagnostics ---
    if not args.no_summary:
        total_with_snippet = sum(1 for j in all_jobs if (j.description_snippet or "").strip())
        by_source = {}
        for j in all_jobs:
            if (j.description_snippet or "").strip():
                by_source[j.source] = by_source.get(j.source, 0) + 1
        if by_source:
            parts = [f"{k}={v}" for k, v in sorted(by_source.items())]
            print(f"Descriptions: with_snippet={total_with_snippet}/{len(all_jobs)} by_source: " + ", ".join(parts))
        else:
            print("Descriptions: with_snippet=0/{len(all_jobs)}")

    # Write raw jobs for inspection (helps tune filters)
    os.makedirs("output", exist_ok=True)
    raw_payload = [j.model_dump() if hasattr(j, "model_dump") else (j.dict() if hasattr(j, "dict") else j.__dict__) for j in all_jobs]
    with open("output/jobs_raw.json", "w", encoding="utf-8") as f:
        json.dump(raw_payload, f, indent=2, default=_json_default)

    if not args.no_summary:
        nonempty_title = sum(1 for j in all_jobs if j.title and j.title.strip())
        eng_like = sum(1 for j in all_jobs if looks_like_engineering(j.title or ""))
        print(f"Titles (non-empty)={nonempty_title} engineering-like={eng_like}/{len(all_jobs)}")
        # Show up to 8 sample titles that did NOT match engineering
        samples = [ (j.title or "").strip() for j in all_jobs if not looks_like_engineering(j.title or "") ][:8]
        if samples:
            print("Example non-matching titles:", "; ".join(samples))

        # Recency diagnostics
        if args.recent_days:
            with_date = sum(1 for j in all_jobs if getattr(j, "posted_at", None) is not None)
            recent_cnt = sum(1 for j in all_jobs if getattr(j, "posted_at", None) is not None and is_recent(getattr(j, "posted_at"), days=args.recent_days))
            print(f"Dates: with_date={with_date}/{len(all_jobs)} recent(<= {args.recent_days}d)={recent_cnt}")

        # Skills diagnostics will be printed after filtering

    # Parse skills filters; if none provided, try defaults file
    if args.skills_any or args.skills_all:
        skills_any = [s.strip().lower() for s in args.skills_any.split(",") if s.strip()] if args.skills_any else []
        skills_all = [s.strip().lower() for s in args.skills_all.split(",") if s.strip()] if args.skills_all else []
        used_defaults = False
    else:
        skills_any, skills_all = _load_default_skills(args.skills_defaults)
        used_defaults = bool(skills_any or skills_all)
        if used_defaults and not args.no_summary:
            print(f"Loaded default skills from {'--skills-defaults' if args.skills_defaults else (os.getenv('RADAR_DEFAULT_SKILLS') or 'config/default_skills.json')}: any={skills_any} all={skills_all}")
    skills_any_set = set(skills_any)
    skills_all_set = set(skills_all)

    # Optional basic filter to keep output focused; tweak flags as needed
    scored: List[tuple[int, NormalizedJob]] = []
    skills_gated_drops = 0
    pre_skills_count = 0

    for j in all_jobs:
        if not _matches_basic(j, junior_only=args.junior_only, relax=args.relax, us_remote_only=False):
            continue
        if args.us_remote_only and not rules_looks_remote_us(j.location, getattr(j, "description_snippet", None)):
            continue
        if args.recent_days:
            pa = getattr(j, "posted_at", None)
            if pa is None:
                if args.require_date:
                    continue  # enforce recency strictly when requested
            else:
                if not is_recent(pa, days=args.recent_days):
                    continue

        pre_skills_count += 1

        # --- Skills scoring / gating ---
        skill_score = 0
        if skills_any_set or skills_all_set:
            hay = f"{(j.title or '')} {(j.description_snippet or '')}".lower()
            # any: count how many ANY terms are present
            if skills_any_set:
                skill_score += sum(1 for term in skills_any_set if term in hay)
            # all: must all be present if specified
            if skills_all_set and not all(term in hay for term in skills_all_set):
                if args.skills_hard:
                    skills_gated_drops += 1
                    continue  # hard drop when --skills-hard and 'all' not satisfied
                # soft mode: no drop; but don't add to score here
            else:
                # reward 'all' presence in the score
                if skills_all_set:
                    skill_score += len(skills_all_set)

            # hard drop if requested and nothing matched in either list
            if args.skills_hard and skill_score == 0:
                skills_gated_drops += 1
                continue

        # In soft mode, give neutral SWE titles a baseline score so they don't all cluster at 0
        if not args.skills_hard and skill_score == 0 and looks_like_engineering(j.title or ""):
            skill_score = 1

        scored.append((skill_score, j))

    # Apply minimum score threshold (after scoring)
    if args.min_score > 0:
        before = len(scored)
        scored = [t for t in scored if t[0] >= args.min_score]
        dropped_by_min = before - len(scored)
    else:
        dropped_by_min = 0

    # Sort by skill score (desc), stable to keep existing order among equals
    scored.sort(key=lambda t: t[0], reverse=True)
    filtered = [j for _, j in scored]

    # Map URL -> (skill_score, best_rank) so we can attach to outputs after dedupe
    score_by_url: Dict[str, int] = {}
    rank_by_url: Dict[str, int] = {}
    for idx, (score, j) in enumerate(scored, start=1):
        if getattr(j, "url", None):
            # Keep the highest score seen for this URL
            prev = score_by_url.get(j.url)
            if prev is None or score > prev:
                score_by_url[j.url] = score
            # Record the first (best) rank position encountered
            if j.url not in rank_by_url:
                rank_by_url[j.url] = idx

    unique = dedupe(filtered)

    if not args.no_summary:
        print(f"Summary: fetched={len(all_jobs)} kept={len(filtered)} unique={len(unique)}")
        if skills_any or skills_all:
            print(f"Skills filters: any={skills_any or '[]'} all={skills_all or '[]'} hard={bool(args.skills_hard)}")
            if 'used_defaults' in locals() and used_defaults:
                print("(skills loaded from defaults file)")
            if pre_skills_count:
                matched_ge_1 = sum(1 for score, _ in scored if score > 0)
                print(f"Skills matches: ≥1={matched_ge_1}/{pre_skills_count}  gated_drops={skills_gated_drops}")
            # Show a quick peek of top-scoring titles
            top_titles = [f"{j.title} [{score}]" for score, j in scored[:5]]
            if top_titles:
                print("Top by skills: " + "; ".join(top_titles))
            print("Ranking: results are sorted by skill_score (desc); neutral SWE titles receive a baseline score in soft mode.")
            if args.min_score > 0:
                print(f"Min-score filter: dropped={dropped_by_min} (threshold={args.min_score})")
            print(f"CSV will be written to: {args.csv_out}")

    os.makedirs("output", exist_ok=True)
    payload = []
    for j in unique:
        # Support both pydantic v2 (model_dump) and v1 (dict)
        if hasattr(j, "model_dump"):
            obj = j.model_dump()
        elif hasattr(j, "dict"):
            obj = j.dict()
        else:
            obj = dict(j.__dict__)

        # Attach skill_score and rank using URL as key (guard against None)
        url_key = getattr(j, "url", None)
        if isinstance(url_key, str) and url_key:
            obj["skill_score"] = score_by_url.get(url_key, 0)
            obj["rank"] = rank_by_url.get(url_key)
        else:
            obj["skill_score"] = 0
            obj["rank"] = None

        # Attach company priority if available
        comp_name = (obj.get("company") or "").strip().lower()
        if comp_name:
            obj["company_priority"] = priority_by_company.get(comp_name)
        else:
            obj["company_priority"] = None

        # Compute posted_days_ago from posted_at if available
        pa = obj.get("posted_at")
        days_ago = None
        try:
            if isinstance(pa, datetime):
                now = datetime.now(timezone.utc)
                # assume naive datetimes are UTC
                pa_dt = pa if pa.tzinfo else pa.replace(tzinfo=timezone.utc)
                days_ago = (now - pa_dt).days
            elif isinstance(pa, str) and pa:
                # try to parse ISO
                dt = datetime.fromisoformat(pa.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - dt).days
        except Exception:
            days_ago = None
        obj["posted_days_ago"] = days_ago

        payload.append(obj)
    with open("output/jobs.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_json_default)

    # --- CSV export ---
    csv_path = args.csv_out
    fieldnames = [
        "rank", "company", "title", "location", "source", "level",
        "posted_at", "posted_days_ago", "skill_score", "company_priority", "url",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.DictWriter(fcsv, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload:
            # Ensure posted_at is a string for CSV
            pa = row.get("posted_at")
            if isinstance(pa, datetime):
                row_pa = pa.isoformat()
            else:
                row_pa = str(pa) if pa is not None else ""
            writer.writerow({
                "rank": row.get("rank", ""),
                "company": row.get("company", ""),
                "title": row.get("title", ""),
                "location": row.get("location", ""),
                "source": row.get("source", ""),
                "level": row.get("level", ""),
                "posted_at": row_pa,
                "posted_days_ago": row.get("posted_days_ago", ""),
                "skill_score": row.get("skill_score", 0),
                "company_priority": row.get("company_priority", ""),
                "url": row.get("url", ""),
            })

if __name__ == "__main__":
    main()
