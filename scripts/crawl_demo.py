#!/usr/bin/env python
from __future__ import annotations
import json, csv, time
from pathlib import Path
from urllib.parse import urlparse, urljoin
import re
from bs4 import BeautifulSoup, Tag

# Helper soup function to safely parse HTML
def _soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "html.parser")
    except Exception:
        return BeautifulSoup(html, "lxml")

from radar.providers.crawler import CrawlFrontier, Fetcher, is_job_page, extract_job, get_extractor_for

def extract_links(html: str, base_url: str) -> list[str]:
    soup = _soup(html)
    links: list[str] = []

    # Only keep links on the same host and that look like job/career pages
    base = urlparse(base_url)
    base_root = f"{base.scheme}://{base.netloc}"

    JOBY = re.compile(r"\b(jobs?|careers?|openings?|positions?|opportunit(?:y|ies)|apply|join[- ]?us)\b|gh_jid=", re.I)

    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag):
            continue
        href_val = a.get("href")
        if not isinstance(href_val, str):
            continue
        href = href_val.strip()
        if not href or href.startswith("javascript:") or href.startswith("mailto:"):
            continue

        # Resolve relative URLs and normalize
        abs_url = urljoin(base_url, href)
        p = urlparse(abs_url)

        # Stay on the same host
        if p.netloc != base.netloc:
            continue

        # Check path/query for job/career hints
        hay = f"{p.path}?{p.query}".lower()
        if not JOBY.search(hay):
            continue

        links.append(abs_url)

    return links

def crawl_once(seeds: list[str], max_pages_per_domain: int = 60) -> list[dict]:
    fetcher = Fetcher()
    frontier = CrawlFrontier(max_depth=3, per_host_delay=1.0)
    frontier.add_seeds(seeds)

    pages_seen_by_host = {}
    results: list[dict] = []

    while True:
        item = frontier.pop()
        if not item:
            break
        host = item.seed_host
        pages_seen_by_host.setdefault(host, 0)
        if pages_seen_by_host[host] >= max_pages_per_domain:
            continue

        delay = frontier.should_delay(host)
        if delay > 0:
            time.sleep(delay)

        status, text, headers = fetcher.get(item.url)
        frontier.mark_fetched(host)

        if status != 200 or not text:
            continue

        pages_seen_by_host[host] += 1

        # Site adapter?
        adapter = get_extractor_for(item.url)
        job = None
        if adapter:
            try:
                job = adapter(text, item.url)
            except Exception:
                job = None
        # Generic path
        if not job and is_job_page(text, item.url):
            job = extract_job(text, item.url)
        if job:
            results.append(job)
            # Don’t expand links from a job detail page (keeps crawl small)
            continue

        # Not a job page — expand links
        links = extract_links(text, item.url)
        frontier.maybe_enqueue_links(item.url, links, seed_host=host, depth=item.depth)

    return results

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Tiny stand-alone job crawler demo")
    ap.add_argument("--seeds", default="seeds_demo.json", help="JSON file with a list of seed URLs")
    ap.add_argument("--max-per-domain", type=int, default=120, help="Page budget per seed host")
    ap.add_argument("--out-csv", default="output/crawler_jobs.csv")
    ap.add_argument("--no-junior-filter", action="store_true",
                    help="Write all engineering-looking jobs (skip junior-only filter)")
    ap.add_argument("--debug-filter", action="store_true",
                    help="Print reasons when candidates are dropped by the junior filter")
    args = ap.parse_args()

    seeds_path = Path(args.seeds)
    seeds = json.loads(seeds_path.read_text())
    assert isinstance(seeds, list) and seeds, "seeds JSON must be a non-empty list of URLs"

    results = crawl_once(seeds, max_pages_per_domain=args.max_per_domain)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)

    # Optional: try to import your rules and apply junior filter
    try:
        from radar.filters.rules import is_junior_title_or_desc, looks_like_engineering
        filtered = []
        for r in results:
            t = (r.get("title") or "").strip()
            desc = r.get("description_html") or ""
            if not looks_like_engineering(t):
                if args.debug_filter:
                    print(f"[filter] drop (non-engineering): {t[:120]}")
                continue

            if args.no_junior_filter:
                # Keep all engineering-looking jobs without junior gating
                filtered.append(r)
                if args.debug_filter:
                    print(f"[filter] keep (engineering, bypass junior): {t[:120]}")
                continue

            ok = is_junior_title_or_desc(t, desc, relaxed=True)
            if ok:
                filtered.append(r)
                if args.debug_filter:
                    print(f"[filter] keep (junior match): {t[:120]}")
            else:
                if args.debug_filter:
                    # Show a small snippet of the description to understand misses
                    snippet = BeautifulSoup(desc, "html.parser").get_text(" ", strip=True) if desc else ""
                    print(f"[filter] drop (no junior signal): {t[:120]}  | desc[:140]='{snippet[:140]}'")
        rows = filtered
    except Exception as e:
        if args.debug_filter:
            print(f"[filter] rules import failed, writing raw results. reason={e}")
        rows = results

    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["company", "title", "url", "date_posted", "location", "provider"])
        for r in rows:
            w.writerow([
                r.get("company", ""),
                r.get("title", ""),
                r.get("url", ""),
                r.get("date_posted", ""),
                r.get("location", ""),
                r.get("provider", "crawler"),
            ])
    print(f"Found {len(results)} jobs; wrote {len(rows)} rows to {args.out_csv}")

if __name__ == "__main__":
    main()