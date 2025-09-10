import argparse
import json
from datetime import datetime, timezone, timedelta

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
from radar.providers import REGISTRY as PROVIDER_REGISTRY
from radar.core.normalize import NormalizedJob
from radar.core.dedupe import deduplicate_jobs as dedupe_normalized
from radar.filters.rules import (
    looks_like_engineering,
    is_junior_title_or_desc,
    looks_remote_us as rules_looks_remote_us,
    is_recent,
)
from radar.config import load_companies
import os
import requests
from bs4 import BeautifulSoup
from radar.db.session import get_session  # Phase 2: persistence
from radar.db.crud import upsert_job      # Phase 2: persistence

# --- provider quota + description top-up helpers ---
_PROVIDER_CAP_ENV = {
    "greenhouse": "RADAR_DESC_CAP_GREENHOUSE",
    "lever": "RADAR_DESC_CAP_LEVER",
    "workday": "RADAR_DESC_CAP_WORKDAY",
    "ashby": "RADAR_DESC_CAP_ASHBY",
    "workable": "RADAR_DESC_CAP_WORKABLE",
}

_DEF_CAP_ENV = "RADAR_DESC_CAP"
_DEF_TIMEOUT_ENV = "RADAR_DESC_TIMEOUT"
_DEF_MAXCHARS_ENV = "RADAR_DESC_MAX_CHARS"


# Junior-focused snippet top-up: invest requests in roles that are likely junior/entry-level
def _junior_top_up_descriptions(
    jobs: List["NormalizedJob"],
    *,
    recent_days: int,
    us_remote_only: bool,
    relax: bool,
) -> tuple[int, Dict[str, int]]:
    """
    Focused snippet fetch: invest requests in roles that are *likely* junior/entry-level,
    so `is_junior_title_or_desc(..., relaxed=True)` has text to work with.
    Returns: (total_fetched, per_provider_counts)
    """
    cap_env = os.getenv("RADAR_JUNIOR_TOPUP_CAP")
    try:
        global_cap = int(cap_env) if cap_env else 150
    except Exception:
        global_cap = 150

    if global_cap <= 0:
        return 0, {}

    timeout = _desc_timeout()
    max_chars = _desc_max_chars()

    # Build candidate pool
    candidates: List[NormalizedJob] = []
    for j in jobs:
        # skip if already has snippet or no URL
        if (j.description_snippet or "").strip() or not getattr(j, "url", None):
            continue

        title = (j.title or "").strip()
        if not title:
            continue

        # Must look vaguely engineering
        if not looks_like_engineering(title):
            continue

        # Exclude obvious senior
        if SENIOR_BLOCK.search(title):
            continue

        # If US-remote-only requested, ensure location + snippet hints (light gate)
        if us_remote_only and not rules_looks_remote_us(getattr(j, "location", ""), getattr(j, "description_snippet", None)):
            # No snippet yet means we only have location; if it's clearly non-US or non-remote, skip
            loc = (getattr(j, "location", "") or "").lower()
            if loc and ("remote" not in loc or ("united states" not in loc and "us" not in loc)):
                continue

        # Recent-days gate (only if date present; we won't fetch to discover date here)
        if recent_days:
            pa = getattr(j, "posted_at", None)
            if pa is not None and not is_recent(pa, days=recent_days):
                continue

        candidates.append(j)

    if not candidates:
        return 0, {}

    # Prioritize explicit junior title signals first
    def _priority_key(job: "NormalizedJob") -> tuple[int, int]:
        t = (job.title or "").lower()
        explicit_junior = 1 if JUNIOR_TITLE.search(t) else 0
        # Prefer shorter titles (often less specialized) as a weak tie-breaker
        return (-explicit_junior, len(t))

    candidates.sort(key=_priority_key)
    plan = candidates[:global_cap]

    def _fetch_and_trim(u: str) -> str:
        try:
            r = requests.get(u, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 JobRadar/1.0"})
            r.raise_for_status()
            txt = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
            return txt[:max_chars]
        except Exception:
            return ""

    fetched_by_provider: Dict[str, int] = {}
    fetched_total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(_fetch_and_trim, j.url): j for j in plan}
        for fut in concurrent.futures.as_completed(futs):
            j = futs[fut]
            snippet = ""
            try:
                snippet = fut.result()
            except Exception:
                snippet = ""
            if snippet:
                try:
                    setattr(j, "description_snippet", snippet)
                    fetched_total += 1
                    pk = (getattr(j, "source", "") or "").lower()
                    if pk:
                        fetched_by_provider[pk] = fetched_by_provider.get(pk, 0) + 1
                except Exception:
                    pass

    return fetched_total, fetched_by_provider


def _cap_for_provider(provider_key: str) -> int:
    env_name = _PROVIDER_CAP_ENV.get(provider_key.lower())
    if env_name:
        v = os.getenv(env_name)
        if v is not None:
            try:
                return int(v)
            except Exception:
                pass
    v = os.getenv(_DEF_CAP_ENV)
    try:
        return int(v) if v is not None else 30
    except Exception:
        return 30


def _desc_timeout() -> float:
    v = os.getenv(_DEF_TIMEOUT_ENV)
    try:
        return float(v) if v is not None else 8.0
    except Exception:
        return 8.0


def _desc_max_chars() -> int:
    v = os.getenv(_DEF_MAXCHARS_ENV)
    try:
        return int(v) if v is not None else 1200
    except Exception:
        return 1200


def _top_up_descriptions(jobs: List["NormalizedJob"], *, junior_only: bool, relax: bool, us_remote_only: bool, recent_days: int) -> None:
    """Fetch additional description snippets per provider up to each provider's cap.
    Only fetch for jobs likely to pass basic filters to conserve requests.
    Mutates `jobs` by setting `description_snippet`.
    """
    # Precompute timeout and max chars
    timeout = _desc_timeout()
    max_chars = _desc_max_chars()

    # Group jobs by provider and count existing snippets
    by_provider: Dict[str, List["NormalizedJob"]] = {}
    with_snip_counts: Dict[str, int] = {}

    for j in jobs:
        pk = (j.source or "").lower()
        if not pk:
            continue
        by_provider.setdefault(pk, []).append(j)
        if (j.description_snippet or "").strip():
            with_snip_counts[pk] = with_snip_counts.get(pk, 0) + 1

    # Build fetch plan: for each provider, compute deficit vs cap and choose candidates
    plan: List["NormalizedJob"] = []
    for pk, lst in by_provider.items():
        cap = _cap_for_provider(pk)
        have = with_snip_counts.get(pk, 0)
        deficit = max(cap - have, 0)
        if deficit <= 0:
            continue
        # Choose candidates without snippets that likely pass basic filters
        candidates = []
        for j in lst:
            if (j.description_snippet or "").strip():
                continue
            # Apply light filters before investing in fetch
            if not _matches_basic(j, junior_only=junior_only, relax=relax, us_remote_only=False):
                continue
            if us_remote_only and not rules_looks_remote_us(j.location, getattr(j, "description_snippet", None)):
                continue
            if recent_days:
                pa = getattr(j, "posted_at", None)
                if pa is not None and not is_recent(pa, days=recent_days):
                    continue
            candidates.append(j)
            if len(candidates) >= deficit:
                break
        plan.extend(candidates)

    if not plan:
        return

    # Concurrently fetch pages and attach snippets
    def _fetch_and_trim(u: str) -> str:
        try:
            r = requests.get(u, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            txt = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
            return txt[:max_chars]
        except Exception:
            return ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(_fetch_and_trim, j.url): j for j in plan if getattr(j, "url", None)}
        for fut in concurrent.futures.as_completed(futs):
            j = futs[fut]
            try:
                snippet = fut.result()
            except Exception:
                snippet = ""
            if snippet:
                try:
                    # Mutate the Pydantic model / object
                    setattr(j, "description_snippet", snippet)
                except Exception:
                    pass

#
# --- Date backfill helpers ----------------------------------------------------
_MONTHS = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

_ISO_DATE = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")
_MON_DD_YYYY = re.compile(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+([0-3]?\d)(?:,)?\s+(20\d{2})\b", re.I)
_POSTED_X_DAYS = re.compile(r"posted\s+(about\s+)?(\d{1,2})\s+day(s)?\s+ago", re.I)
_X_DAYS_AGO = re.compile(r"\b(\d{1,2})\s+day(s)?\s+ago\b", re.I)


def _parse_posted_at_from_text(text: str) -> datetime | None:
    """Best-effort: parse a posting date from visible page text.
    Returns naive UTC datetime (no tz) on success, else None.
    """
    if not text:
        return None
    try:
        # 1) ISO date first (YYYY-MM-DD)
        m = _ISO_DATE.search(text)
        if m:
            y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return datetime(y, mo, dd)
        # 2) Month DD, YYYY
        m = _MON_DD_YYYY.search(text)
        if m:
            mon, dd, y = m.group(1), int(m.group(2)), int(m.group(3))
            mon_key = mon.lower()
            mo = _MONTHS.get(mon_key[:3], _MONTHS.get(mon_key, 0))
            if mo:
                return datetime(y, mo, dd)
        # 3) "Posted X days ago" (or just "X days ago")
        m = _POSTED_X_DAYS.search(text) or _X_DAYS_AGO.search(text)
        if m:
            days = int(m.group(2) if m.re is _POSTED_X_DAYS else m.group(1))
            dt = datetime.now(timezone.utc) - timedelta(days=days)
            return dt.replace(tzinfo=None)
    except Exception:
        pass
    return None


def _backfill_posted_at(jobs: List["NormalizedJob"], *, cap: int | None = None, quiet: bool = False) -> tuple[int, dict[str, int]]:
    """Fetch pages for jobs missing posted_at and best-effort parse a date.
    Uses existing description_snippet text when available to avoid extra HTTP.
    Returns (total_backfilled, counts_by_provider).
    Controlled by env RADAR_DATE_BACKFILL_CAP (default 120) if cap not provided.
    """
    try:
        max_total = int(os.getenv("RADAR_DATE_BACKFILL_CAP", "120")) if cap is None else int(cap)
    except Exception:
        max_total = 120
    if max_total <= 0:
        return 0, {}

    timeout = _desc_timeout()
    counts: dict[str, int] = {}
    targets: list[NormalizedJob] = []
    for j in jobs:
        if getattr(j, "posted_at", None) is None and getattr(j, "url", None):
            targets.append(j)
            if len(targets) >= max_total:
                break

    def _fetch_text_for(j: "NormalizedJob") -> str:
        # Prefer already-fetched snippet text if present
        snip = (getattr(j, "description_snippet", "") or "").strip()
        if snip:
            return snip
        try:
            r = requests.get(j.url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 JobRadar/1.0"})
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
        except Exception:
            return ""

    updated = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(_fetch_text_for, j): j for j in targets}
        for fut in concurrent.futures.as_completed(futs):
            j = futs[fut]
            try:
                txt = fut.result()
            except Exception:
                txt = ""
            if not txt:
                continue
            dt = _parse_posted_at_from_text(txt)
            if dt is None:
                continue
            try:
                setattr(j, "posted_at", dt)
                updated += 1
                pk = (getattr(j, "source", "") or "").lower()
                if pk:
                    counts[pk] = counts.get(pk, 0) + 1
            except Exception:
                pass

    if not quiet and updated:
        pass  # printing handled by caller
    return updated, counts

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

    # Profiles (preset flags)
    parser.add_argument("--profile", choices=["apply-now", "research"], default=None,
                        help="Preset of sensible flags: 'apply-now' -> US remote, 14 days, junior-only, relax, min-score 1; 'research' -> 30 days, no min-score")

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
    parser.add_argument("--csv-columns", type=str, default="",
                        help="Comma-separated CSV columns to write and order. Default includes rank, company, title, location, source, provider, company_token, level, posted_at, posted_days_ago, skill_score, company_priority, url")
    # Persistence
    parser.add_argument("--save", action="store_true",
                        help="Persist kept jobs into the database (requires DATABASE_URL)")
    parser.add_argument(
        "--providers",
        default="greenhouse",
        help="Comma-separated provider list to enable (e.g., 'greenhouse,lever'). Use 'all' to enable everything. Default: greenhouse",
    )

    args = parser.parse_args()

    # Which providers are enabled for this run?
    if args.providers and args.providers.strip().lower() in ("all", "*"):
        enabled_providers = {k.lower() for k in PROVIDER_REGISTRY.keys()}
    elif args.providers:
        enabled_providers = {p.strip().lower() for p in args.providers.split(",") if p.strip()}
    else:
        # Fallback: enable all if nothing provided (shouldn't happen with our default)
        enabled_providers = {k.lower() for k in PROVIDER_REGISTRY.keys()}

    # Apply profile defaults (user flags still override if explicitly set)
    if args.profile == "apply-now":
        if not args.us_remote_only:
            args.us_remote_only = True
        if args.recent_days == 0:
            args.recent_days = 14
        if not args.junior_only:
            args.junior_only = True
        if not args.relax:
            args.relax = True
        if args.min_score == 0:
            args.min_score = 1
    elif args.profile == "research":
        if args.recent_days == 0:
            args.recent_days = 30
        # leave other flags as-is to allow custom exploration

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
        print("Enabled providers:", ", ".join(sorted(enabled_providers)) or "(none)")

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

    # Map company name -> token for output convenience (e.g., board token)
    token_by_company: Dict[str, str] = {}
    for c in companies:
        name = (c.get("company") or "").strip()
        if name:
            tk = c.get("token")
            if tk:
                token_by_company[name.lower()] = str(tk)

    tasks = []
    for company in companies:
        provider_key = (company.get("provider") or "").lower()
        if not provider_key or provider_key not in PROVIDER_REGISTRY:
            print(f"⚠️ Skipping company '{company.get('company')}' due to missing or unknown provider: {provider_key}")
            continue
        if provider_key not in enabled_providers:
            # Provider is known but not enabled for this run
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

    # Provider distribution before snippet top-up (after fetch)
    if not args.no_summary:
        prov_counts: Dict[str, int] = {}
        for j in all_jobs:
            pk = (j.source or "").lower()
            if pk:
                prov_counts[pk] = prov_counts.get(pk, 0) + 1
        if prov_counts:
            parts = [f"{k}={v}" for k, v in sorted(prov_counts.items())]
            print("Providers (raw fetch): " + ", ".join(parts))

    # Junior-focused snippet top-up (global cap): give relaxed junior logic text to read
    jr_fetched_total, jr_by_provider = _junior_top_up_descriptions(
        all_jobs,
        recent_days=args.recent_days,
        us_remote_only=args.us_remote_only,
        relax=args.relax,
    )
    if not args.no_summary:
        if jr_fetched_total:
            parts = ", ".join(f"{k}={v}" for k, v in sorted(jr_by_provider.items()))
            print(f"Junior top-up: fetched_snippets={jr_fetched_total} by_source: {parts or '(none)'} (cap={os.getenv('RADAR_JUNIOR_TOPUP_CAP') or 150})")
        else:
            print("Junior top-up: fetched_snippets=0")
    # Per-provider quota: top up descriptions so non-Greenhouse providers get coverage
    _top_up_descriptions(
        all_jobs,
        junior_only=args.junior_only,
        relax=args.relax,
        us_remote_only=args.us_remote_only,
        recent_days=args.recent_days,
    )

    # Date backfill (best-effort): populate missing posted_at from page text
    backfilled_total, backfilled_by = _backfill_posted_at(all_jobs)
    if not args.no_summary:
        if backfilled_total:
            parts = ", ".join(f"{k}={v}" for k, v in sorted(backfilled_by.items())) or "(none)"
            print(f"Date backfill: updated={backfilled_total} by_source: {parts} (cap={os.getenv('RADAR_DATE_BACKFILL_CAP') or 120})")
        else:
            print("Date backfill: updated=0")

    # --- Description snippet diagnostics ---
    if not args.no_summary:
        total_with_snippet = sum(1 for j in all_jobs if (j.description_snippet or "").strip())
        by_source = {}
        for j in all_jobs:
            if (j.description_snippet or "").strip():
                by_source[j.source] = by_source.get(j.source, 0) + 1
        if by_source:
            parts = []
            for k, v in sorted(by_source.items()):
                parts.append(f"{k}={v} (cap={_cap_for_provider(k)})")
            print(f"Descriptions: with_snippet={total_with_snippet}/{len(all_jobs)} by_source: " + ", ".join(parts))
        else:
            print(f"Descriptions: with_snippet=0/{len(all_jobs)}")

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
        # Providers after basic filters (pre-skills)
        prov_after_basic: Dict[str, int] = {}
        for _, j in scored:
            pk = (j.source or "").lower()
            if pk:
                prov_after_basic[pk] = prov_after_basic.get(pk, 0) + 1
        if prov_after_basic:
            parts = [f"{k}={v}" for k, v in sorted(prov_after_basic.items())]
            print("Providers (after basic filters): " + ", ".join(parts))

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
            if args.profile:
                print(f"Profile: {args.profile}")

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

        # Attach provider (same as source) and company_token if available
        obj["provider"] = obj.get("source")
        if comp_name:
            obj["company_token"] = token_by_company.get(comp_name)
        else:
            obj["company_token"] = None

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

    # --- Optional: persist kept jobs to the database ---
    if args.save:
        try:
            # Lazy imports to keep CLI fast when not saving
            from urllib.parse import urlparse
            from radar.db.session import get_session
            from radar.db.crud import upsert_job

            def _to_naive_utc(dt_val):
                # Accept datetime or ISO string; return naive UTC datetime or None
                if isinstance(dt_val, datetime):
                    return dt_val if dt_val.tzinfo is None else dt_val.astimezone(timezone.utc).replace(tzinfo=None)
                if isinstance(dt_val, str) and dt_val:
                    try:
                        dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
                        return dt if dt.tzinfo is None else dt.astimezone(timezone.utc).replace(tzinfo=None)
                    except Exception:
                        return None
                return None

            def _pick_external_id(row: dict) -> str | None:
                # Try common keys first; otherwise derive a stable-ish ID from the URL
                for k in (
                    "external_id",
                    "id",
                    "job_id",
                    "greenhouse_id",
                    "gh_id",
                    "lever_id",
                    "workday_id",
                    "ashby_id",
                    "workable_id",
                ):
                    v = row.get(k)
                    if v is not None and str(v).strip():
                        return str(v)
                url = (row.get("url") or "").strip()
                if not url:
                    return None
                try:
                    path = urlparse(url).path.rstrip("/")
                    tail = path.split("/")[-1]
                    return tail or url  # last path segment or fallback to full URL
                except Exception:
                    return url

            def _infer_is_remote(row: dict) -> bool:
                loc = row.get("location") or ""
                desc = row.get("description_snippet") or ""
                try:
                    return bool(rules_looks_remote_us(loc, desc))
                except Exception:
                    # Conservative fallback
                    s = f"{loc} {desc}".lower()
                    return "remote" in s and ("united states" in s or "usa" in s or "us" in s)

            # Build a quick matcher from the run's skill lists (if provided/loaded)
            terms_for_match = set()
            try:
                terms_for_match |= set(skills_any_set)
                terms_for_match |= set(skills_all_set)
            except Exception:
                pass

            def _matched_skills(row: dict) -> list[str]:
                if not terms_for_match:
                    return []
                hay = f"{row.get('title','')} {row.get('description_snippet','')}".lower()
                return sorted([t for t in terms_for_match if t in hay])

            saved = 0
            total = 0
            errors = 0

            with get_session() as session:
                for row in payload:
                    total += 1
                    company_name = (row.get("company") or "").strip()
                    provider = (row.get("provider") or row.get("source") or "").strip().lower()
                    url = (row.get("url") or "").strip()
                    title = (row.get("title") or "").strip()

                    if not (company_name and provider and url and title):
                        errors += 1
                        continue

                    job_data = {
                        "provider": provider,
                        "external_id": _pick_external_id(row),
                        "url": url,
                        "company": company_name,        # upsert_job accepts a plain name; will create/lookup Company
                        "title": title,
                        "location": row.get("location"),
                        "is_remote": _infer_is_remote(row),
                        "level": (row.get("level") or "unknown").lower(),
                        "posted_at": _to_naive_utc(row.get("posted_at")),
                        "description": row.get("description_snippet") or row.get("description") or None,
                        "skills": _matched_skills(row),
                        # optional extras our model supports
                        "function": row.get("function"),
                        "seniority_score": row.get("seniority_score"),
                    }

                    try:
                        if upsert_job(job_data=job_data, session=session):
                            saved += 1
                    except Exception:
                        errors += 1
                        # Uncomment to debug persisting issues:
                        # print(f"[persist] error for {company_name} / {title}: {e}")

            print(f"Persisted {saved}/{total} jobs to the database." + (f" (errors={errors})" if errors else ""))

        except Exception as e:
            print(f"DB save skipped due to error: {e}")

    # --- CSV export ---
    csv_path = args.csv_out
    # Determine CSV columns (allow overrides)
    default_cols = [
        "rank", "company", "title", "location", "source", "provider", "company_token", "level",
        "posted_at", "posted_days_ago", "skill_score", "company_priority", "url",
    ]
    if args.csv_columns:
        fieldnames = [c.strip() for c in args.csv_columns.split(",") if c.strip()]
    else:
        fieldnames = default_cols

    with open(csv_path, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.DictWriter(fcsv, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload:
            # Copy row to a mutable map and ensure posted_at string formatting if requested
            val_map = dict(row)
            pa_val = row.get("posted_at")
            if isinstance(pa_val, datetime):
                val_map["posted_at"] = pa_val.isoformat()
            elif pa_val is None:
                val_map["posted_at"] = ""
            # Build output row in requested column order
            row_out = {col: val_map.get(col, "") for col in fieldnames}
            writer.writerow(row_out)

if __name__ == "__main__":
    main()
