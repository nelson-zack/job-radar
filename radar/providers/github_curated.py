from __future__ import annotations

"""
Lightweight provider that scrapes curated GitHub repos which track New‑Grad roles.

This is intentionally self-contained so we can call it from ad-hoc scripts or
wire it into the normal providers registry later.

Sources (curated spreadsheets / READMEs):
  - https://github.com/SimplifyJobs/New-Grad-Positions
  - https://github.com/vanshb03/New-Grad-2026
  - https://github.com/speedyapply/2026-SWE-College-Jobs/blob/main/NEW_GRAD_USA.md
  - Also handles embedded HTML tables automatically
"""

from dataclasses import dataclass
from typing import Iterable, Iterator, List, Dict, Optional, Tuple, Set
import hashlib
import logging
import os
import re
import time
from urllib.parse import urlparse
from urllib.parse import urljoin
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from radar.core.date_parse import parse_curated_date
from radar.core.github_dates import GitContext, infer_posted_at, log_inference_metrics

# Prefer "Apply" links in HTML tags
def _pick_href_from_tag(tag: Tag) -> Optional[str]:
    """Return href preferring anchors whose text mentions 'apply'."""
    if not isinstance(tag, Tag):
        return None
    anchors = tag.find_all("a")
    best = None
    for a in anchors:
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if isinstance(href, str):
            if best is None:
                best = href
            text = (a.get_text(strip=True) or "").lower()
            if "apply" in text:
                return href
    return best

log = logging.getLogger(__name__)

# --------- Helpers -----------------------------------------------------------

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
WS_RE = re.compile(r"\s+")

REMOTE_HINTS = (
    "remote",
    "us-remote",
    "us remote",
    "united states (remote)",
    "anywhere in the us",
    "usa (remote)",
    "remote, us",
)

LEVEL_JUNIOR_HINTS = (
    "new grad",
    "new‑grad",
    "entry",
    "entry level",
    "entry-level",
    "level 1",
    "engineer i",
    "software engineer i",
    "associate",
    "university",
    "graduate program",
    "associate software engineer",
)

UNWANTED_REGIONS = (
    "india",
    "emea",
    "apac",
    "europe only",
    "singapore",
    "china",
    "japan",
    "korea",
    "latam",
    "canada",
    "canada only",
    "europe",
)

USER_AGENT = "job-radar/gh-curated (+https://github.com/nelson-zack/job-radar)"
REQ_TIMEOUT = 20

# Keep only query params that help identify the posting (drop trackers)
KEEP_QS_KEYS = {"gh_jid"}  # e.g., Greenhouse posting id

def _canonicalize_url(u: str) -> Optional[str]:
    """
    Normalize tracking-heavy URLs and drop ones that aren't real postings.
    - Strip UTM/ref params everywhere.
    - Keep only whitelisted query keys (e.g., gh_jid).
    - For simplify.jobs:
        * keep only direct posting URLs (must have gh_jid),
        * drop company overview pages like /c/<Company>.
    """
    try:
        sp = urlsplit(u)
        host = (sp.hostname or "").lower()

        # Clean querystring
        q = dict(parse_qsl(sp.query, keep_blank_values=True))
        keep = {k: v for k, v in q.items() if k in KEEP_QS_KEYS}

        # Drop Simplify "company" pages; keep only if gh_jid is present
        if host == "simplify.jobs":
            parts = sp.path.strip("/").split("/", 1)
            if parts:
                first = parts[0]
                # Keep Simplify landing pages ("/p/" or "/c/") even when there
                # isn't a gh_jid query param. These still represent concrete job
                # postings and should not be dropped during canonicalization.
                if first in {"p", "c"}:
                    pass
                elif "gh_jid" not in keep:
                    return None

        # Rebuild URL with trimmed query
        cleaned = urlunsplit((sp.scheme, sp.netloc, sp.path, urlencode(keep, doseq=True), sp.fragment))

        # Ensure https
        if cleaned.startswith("http://"):
            cleaned = "https://" + cleaned[len("http://"):]
        return cleaned
    except Exception:
        return u

def _clean_location(loc: str) -> str:
    """
    Tidy up common artifacts (e.g., duplicated 'Remote' tokens).
    """
    s = WS_RE.sub(" ", (loc or "").strip())
    # collapse repeated 'Remote' words like 'Remote Remote' or ', Remote'
    s = re.sub(r"(,\s*)?remote(\s*,\s*remote)+", " remote", s, flags=re.I)
    s = re.sub(r"\bremote\s+in\s+usa\b", "Remote (US)", s, flags=re.I)
    return s

def _clean_company_name(name: str) -> str:
    """Strip leading bullets/arrows/emojis and collapse whitespace."""
    s = (name or "").strip()
    # remove leading non-word symbols like '↳', '*', '-', '•'
    s = re.sub(r"^[^\w\(\[]+", "", s)
    s = WS_RE.sub(" ", s).strip()
    return s

def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _extract_link(md_cell: str) -> Tuple[str, Optional[str]]:
    """
    Return (display_text, url or None) from a markdown cell that may contain a link.
    Prefer links whose text contains 'apply'.
    """
    cell = (md_cell or "").strip()
    # Gather all markdown links
    matches = list(_LINK_RE.finditer(cell))
    if matches:
        # Try to find one whose text mentions "apply"
        for m in matches:
            text = m.group(1).strip()
            if "apply" in text.lower():
                return text, m.group(2).strip()
        # Fall back to first link
        m0 = matches[0]
        return m0.group(1).strip(), m0.group(2).strip()
    # sometimes the cell is just a URL
    if cell.startswith("http://") or cell.startswith("https://"):
        return cell, cell
    return cell, None


def _is_remote(loc_text: str) -> bool:
    lt = loc_text.lower()
    return any(h in lt for h in REMOTE_HINTS)



def _looks_us_only(loc_text: str) -> bool:
    """
    Heuristic to decide whether a location is US-friendly.

    Rules:
    - If it explicitly mentions a non‑US region (e.g., Canada/EMEA/APAC), return False.
    - If it clearly mentions US (tokens like US, U.S., USA, United States, or patterns like "(US)", "US-Remote"),
      return True.
    - Otherwise, if it's marked Remote but does NOT mention an explicit non‑US region, treat as US‑friendly.
    - Else False.
    """
    lt = (loc_text or "").lower()

    # 1) Explicit non‑US markers kill it
    if any(bad in lt for bad in UNWANTED_REGIONS):
        return False

    # 2) Normalize punctuation to spaces, then look for US tokens as whole words
    norm = re.sub(r"[^a-z]+", " ", lt)  # keep only letters as word separators
    if re.search(r"\b(us|u s|u s a|usa|united states)\b", norm):
        return True

    # Also catch common punctuated patterns without relying on word boundaries
    if re.search(r"\(us\)|us-remote|remote-us|us only|us-based", lt):
        return True

    # 3) If it's remote and there were no explicit non‑US hints, accept as US‑friendly
    if "remote" in lt:
        return True

    return False


def _junior_level_from_text(text: str) -> str:
    lt = text.lower()
    return "junior" if any(h in lt for h in LEVEL_JUNIOR_HINTS) else "unknown"


def _hash_external(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _get(url: str) -> str:
    log.debug("GET %s", url)
    resp = requests.get(url, timeout=REQ_TIMEOUT, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def _candidate_raw_urls(src: str) -> List[str]:
    """
    Build a list of possible raw.githubusercontent.com URLs for a given GitHub UI URL.
    Tries both main and master branches, and common file paths (README.md, NEW_GRAD_USA.md).
    """
    s = src.rstrip("/")
    if s.startswith("https://raw.githubusercontent.com/"):
        # Already a raw URL; try it as-is
        return [s]

    if not s.startswith("https://github.com/"):
        # Non-GitHub URL; return as-is
        return [s]

    # Normalize GitHub URL to owner/repo[/blob/<branch>/<path>]
    rel = s.replace("https://github.com/", "")
    candidates: List[str] = []

    # If specific blob path is provided, convert and try both main/master
    if "/blob/" in rel:
        left, right = rel.split("/blob/", 1)  # left = owner/repo, right = branch/path
        # right is "<branch>/<path...>"
        parts = right.split("/", 1)
        if len(parts) == 2:
            branch, path = parts
        else:
            branch, path = parts[0], "README.md"
        for b in (branch, "main", "master"):
            candidates.append(f"https://raw.githubusercontent.com/{left}/{b}/{path}")
    else:
        # Repo root; assume README.md on main/master
        for b in ("main", "master"):
            candidates.append(f"https://raw.githubusercontent.com/{rel}/{b}/README.md")
            # Some curated repos keep lists under custom filenames
            candidates.append(f"https://raw.githubusercontent.com/{rel}/{b}/NEW_GRAD_USA.md")
            candidates.append(f"https://raw.githubusercontent.com/{rel}/{b}/US-NEW-GRAD.md")

    # De-duplicate while preserving order
    seen: Set[str] = set()
    uniq: List[str] = []
    for u in candidates:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq


def _fetch_markdown(src: str) -> Optional[str]:
    """
    Try a series of candidate raw URLs for a given GitHub source and return the first that fetches.
    """
    for url in _candidate_raw_urls(src):
        try:
            return _get(url)
        except Exception as e:
            log.debug("Fetch failed for %s (%s); trying next candidate", url, e)
            continue
    return None


def _normalize_source_url(url: str) -> str:
    """
    Kept for backward-compat compatibility. Returns the first candidate raw URL.
    For full branch/path handling, see `_candidate_raw_urls` / `_fetch_markdown`.
    """
    return _candidate_raw_urls(url)[0]


def _flag_github_date_inference() -> bool:
    return os.getenv("GITHUB_DATE_INFERENCE", "false").lower() == "true"


def _flag_github_curated_date_scrape() -> bool:
    return os.getenv("GITHUB_CURATED_DATE_SCRAPE", "false").lower() == "true"


# --------- HTML table parsing (for READMEs that embed HTML) --------------

def _iter_rows_from_html_tables(md: str) -> Iterator[ParsedRow]:
    """
    Some curated READMEs use raw HTML tables inside markdown.
    Parse & yield rows using BeautifulSoup if a <table> is present.
    """
    if "<table" not in md.lower():
        return
        yield  # make this a generator even when not used

    # Try lxml first for speed; fall back to the builtin parser
    try:
        soup = BeautifulSoup(md, "lxml")
    except Exception:
        soup = BeautifulSoup(md, "html.parser")

    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue

        # Build header map
        headers: list[str] = []
        ths = table.find_all("th")
        if ths:
            headers = [th.get_text(strip=True) for th in ths if isinstance(th, Tag)]
        if not headers:
            # try first row td as header
            first_row = table.find("tr")
            if not isinstance(first_row, Tag):
                continue
            tds = first_row.find_all("td")
            headers = [td.get_text(strip=True) for td in tds if isinstance(td, Tag)]

        col = _find_col_idx([h.strip() for h in headers])
        if not col:
            continue

        # Iterate rows (skip header row)
        rows = table.find_all("tr")
        iter_rows = rows[1:] if len(rows) > 1 else rows
        for tr in iter_rows:
            if not isinstance(tr, Tag):
                continue
            tds = tr.find_all(["td", "th"])  # type: ignore[list-item]
            if not tds:
                continue
            cells = [td.get_text(" ", strip=True) for td in tds if isinstance(td, Tag)]

            # Safe indexing with fallbacks
            company = _clean_company_name(cells[col.get("company", 0)] if len(cells) else "")
            title = cells[col.get("title", 0)] if len(cells) else ""
            location = (
                cells[col["location"]] if "location" in col and len(cells) > col["location"] else ""
            )
            date_val = (
                cells[col["date"]] if "date" in col and len(cells) > col["date"] else ""
            )
            age_val = (
                cells[col["age"]] if "age" in col and len(cells) > col["age"] else ""
            )

            # Prefer explicit link cell; otherwise search links in row
            url: Optional[str] = None
            if "url" in col and len(tds) > col["url"]:
                td_cell = tds[col["url"]]
                if isinstance(td_cell, Tag):
                    url = _pick_href_from_tag(td_cell)
            url = url or _pick_href_from_tag(tr)

            yield ParsedRow(company=company, title=title, location=location, url=url, date=date_val, age=age_val)


# --------- Markdown table parsing -------------------------------------------

@dataclass
class ParsedRow:
    company: str
    title: str
    location: str
    url: Optional[str]
    date: str = ""
    age: str = ""
    posted_at: str = ""


def _iter_md_tables(md: str) -> Iterator[list[list[str]]]:
    """
    Yield markdown tables as a list of rows (each row is list of cells).
    Very simple parser: looks for header lines with | and a separator of ---.
    """
    lines = [ln.rstrip() for ln in md.splitlines()]
    i = 0
    n = len(lines)
    while i < n:
        if "|" in lines[i]:
            # find separator within next 2 lines
            j = i + 1
            sep_found = False
            while j < min(i + 3, n):
                if set(lines[j].strip()) <= {"|", " ", ":", "-"} and "---" in lines[j]:
                    sep_found = True
                    break
                j += 1
            if sep_found:
                # collect table until blank / non-pipe line
                header = lines[i]
                k = j + 1
                rows: list[str] = []
                while k < n and lines[k].strip().startswith("|"):
                    rows.append(lines[k])
                    k += 1
                # build grid
                grid = [ _split_row(header) ]
                grid += [ _split_row(r) for r in rows ]
                yield grid
                i = k
                continue
        i += 1


def _split_row(row: str) -> list[str]:
    # strip leading/trailing pipes, then split
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def _find_col_idx(header_cells: list[str]) -> Dict[str, int]:
    idx: Dict[str, int] = {}
    for i, h in enumerate(header_cells):
        hl = h.lower()
        if any(k in hl for k in ("company", "organization", "employer")):
            idx.setdefault("company", i)
        if any(k in hl for k in ("role", "position", "title")):
            idx.setdefault("title", i)
        if any(k in hl for k in ("location", "locations")):
            idx.setdefault("location", i)
        if any(k in hl for k in ("apply", "link", "url", "posting")):
            idx.setdefault("url", i)
        if any(k in hl for k in ("date", "posted", "posted on", "updated", "last update", "last updated")):
            idx.setdefault("date", i)
        if any(k in hl for k in ("age", "ago")):
            idx.setdefault("age", i)
    return idx


def _iter_rows_from_md(md: str) -> Iterator[ParsedRow]:
    for grid in _iter_md_tables(md):
        if not grid or len(grid) < 2:
            continue
        header = grid[0]
        col = _find_col_idx(header)
        if not col:
            continue
        for r in grid[1:]:
            # pad short rows
            if len(r) < len(header):
                r = r + [""] * (len(header) - len(r))
            company = r[col.get("company", 0)]
            title = r[col.get("title", 0)]
            location = r[col.get("location", 0)] if "location" in col else ""
            url_cell = r[col.get("url", 0)] if "url" in col else ""
            _, url = _extract_link(url_cell)
            # Some lists put the link in the title cell
            if not url:
                _, url = _extract_link(title)
            # Clean company/title plain text (remove markdown)
            company = _clean_company_name(_LINK_RE.sub(lambda m: m.group(1), company).strip())
            title = _LINK_RE.sub(lambda m: m.group(1), title).strip()
            date_val = r[col.get("date", 0)] if "date" in col else ""
            age_val = r[col.get("age", 0)] if "age" in col else ""
            yield ParsedRow(company=company, title=title, location=location, url=url, date=date_val, age=age_val)


def _iter_rows_from_bullets(md: str) -> Iterator[ParsedRow]:
    """
    Fallback parser: scan bullet/numbered lists for markdown links.
    Yields ParsedRow with company/title inferred from link text (location unknown).
    """
    for ln in md.splitlines():
        ls = ln.lstrip()
        if not (ls.startswith("- ") or ls.startswith("* ") or re.match(r"^\d+\.\s", ls)):
            continue
        m = _LINK_RE.search(ls)
        if not m:
            continue
        text = m.group(1).strip()
        url = m.group(2).strip()
        # Reasonable split heuristic: "Company — Title" or "Company - Title"
        company, title = text, text
        if "—" in text:
            parts = [p.strip() for p in text.split("—", 1)]
            if len(parts) == 2:
                company, title = parts
        elif " - " in text:
            parts = [p.strip() for p in text.split(" - ", 1)]
            if len(parts) == 2:
                company, title = parts
        yield ParsedRow(company=company, title=title, location="", url=url)


# --------- Public API --------------------------------------------------------

DEFAULT_SOURCES = (
    "https://github.com/SimplifyJobs/New-Grad-Positions",
    "https://github.com/vanshb03/New-Grad-2026",
    "https://github.com/speedyapply/2026-SWE-College-Jobs/blob/main/NEW_GRAD_USA.md",
)


def fetch_curated_github_jobs(
    sources: Iterable[str] = DEFAULT_SOURCES,
    only_remote: bool = True,
    us_only: bool = True,
    provider_label: str = "github",
    git_ctx: Optional[GitContext] = None,
    enable_scrape: Optional[bool] = None,
    enable_inference: Optional[bool] = None,
) -> List[Dict]:
    """
    Fetch and normalize jobs from curated GitHub lists.

    Returns list of dicts consumable by the DB upsert (keys align with our pipeline):
      - provider: "github"
      - external_id: short hash of the URL
      - company: display name
      - company_token: slug
      - title
      - url
      - location
      - is_remote
      - level: "junior" | "unknown"
    """
    jobs: List[Dict] = []
    seen_urls: Set[str] = set()
    inference_enabled = (
        _flag_github_date_inference() if enable_inference is None else enable_inference
    )
    scrape_enabled = (
        _flag_github_curated_date_scrape() if enable_scrape is None else enable_scrape
    )
    parsed_dates = 0
    inferred_dates = 0
    undated_after = 0
    for src in sources:
        md = _fetch_markdown(src)
        if not md:
            log.warning("Failed to fetch %s (no candidate URLs succeeded)", src)
            continue

        produced = 0

        def _process_row(row: ParsedRow) -> None:
            nonlocal produced, parsed_dates, inferred_dates, undated_after
            if not row.url:
                return
            row_url = _canonicalize_url(row.url)
            if not row_url:
                return
            if row_url in seen_urls:
                return
            comp = _clean_company_name(row.company or "")
            title = row.title or ""
            location = row.location or ""
            location = _clean_location(location)

            is_remote = _is_remote(location) or ("remote" in title.lower())
            if only_remote and not is_remote:
                return

            # Be strict: if we can't positively confirm US, drop the row (avoids "Remote in Canada", EU-only, etc.)
            if us_only and not _looks_us_only(location):
                return

            level = _junior_level_from_text(f"{title} {location}")
            slug = _slugify(comp) if comp else ""
            if not slug:
                host = (urlparse(row_url).hostname or "unknown").split(":")[0]
                slug = _slugify(host) or "unknown"
            company_token = slug
            external_id = _hash_external(row_url)

            payload = {
                "provider": provider_label,
                "external_id": external_id,
                "company": comp or company_token,
                "company_token": company_token,
                "title": title if title else "Software Engineer (New Grad)",
                "url": row_url,
                "location": location,
                "is_remote": bool(is_remote),
                "level": level,
            }

            date_candidates = []
            for attr in ("date", "age", "posted_at"):
                val = getattr(row, attr, None)
                if val:
                    date_candidates.append(val)

            if scrape_enabled:
                for candidate in date_candidates:
                    clean = _LINK_RE.sub(lambda m: m.group(1), str(candidate)).strip().strip('*_ ')
                    parsed_dt = parse_curated_date(clean)
                    if parsed_dt is not None:
                        payload["posted_at"] = parsed_dt
                        parsed_dates += 1
                        break

            if payload.get("posted_at") is None:
                if inference_enabled:
                    inferred_dt = infer_posted_at(external_id, git_ctx) if git_ctx is not None else None
                    if inferred_dt is not None:
                        payload["posted_at"] = inferred_dt
                        inferred_dates += 1
                    else:
                        undated_after += 1
                else:
                    undated_after += 1

            jobs.append(payload)
            seen_urls.add(row_url)
            produced += 1

        # 1) HTML tables embedded in README
        for r in _iter_rows_from_html_tables(md):
            _process_row(r)

        # 2) Markdown tables
        for r in _iter_rows_from_md(md):
            _process_row(r)

        # 3) Fallback: bullet lists
        if produced == 0:
            for r in _iter_rows_from_bullets(md):
                _process_row(r)

    if inference_enabled:
        log_inference_metrics(log, provider_label, inferred_dates, undated_after, len(jobs))

    if scrape_enabled:
        log.info(
            "github-date-scrape provider=%s parsed=%s inferred=%s undated=%s total=%s",
            provider_label,
            parsed_dates,
            inferred_dates,
            undated_after,
            len(jobs),
        )

    return jobs
