from __future__ import annotations
import time, heapq, hashlib
from dataclasses import dataclass, field
from typing import Iterable, Set, Tuple, Dict
from urllib.parse import urlparse, urljoin

ALLOWED_PATH_HINTS = ("career", "careers", "job", "jobs", "opportun", "opening", "position")

@dataclass(order=True)
class _QItem:
    priority: int
    t_enq: float = field(compare=False)
    url: str = field(compare=False)
    depth: int = field(compare=False)
    seed_host: str = field(compare=False)

class CrawlFrontier:
    """Simple domain-scoped priority queue with dedupe & politeness windows."""
    def __init__(self, max_depth: int = 3, per_host_delay: float = 1.0):
        self.max_depth = max_depth
        self.per_host_delay = per_host_delay
        self.q: list[_QItem] = []
        self.seen: Set[str] = set()
        self.host_next_at: Dict[str, float] = {}

    def add_seeds(self, seeds: Iterable[str]) -> None:
        now = time.time()
        for s in seeds:
            u = self._canon(s)
            if not u or u in self.seen:
                continue
            self.seen.add(u)
            prio = self._priority(u)
            heapq.heappush(self.q, _QItem(prio, now, u, 0, urlparse(u).netloc))

    def _priority(self, url: str) -> int:
        """Lower is earlier. Prefer URLs with 'jobs/careers' hints."""
        path = urlparse(url).path.lower()
        has_hint = any(h in path for h in ALLOWED_PATH_HINTS)
        # negative for higher priority
        return -2 if has_hint else -1

    def _canon(self, url: str) -> str | None:
        try:
            # normalize: strip fragments, default scheme
            parsed = urlparse(url if "://" in url else f"https://{url}")
            if not parsed.netloc:
                return None
            path = parsed.path or "/"
            return parsed._replace(fragment="", query=parsed.query, path=path).geturl()
        except Exception:
            return None

    def should_delay(self, host: str) -> float:
        now = time.time()
        nxt = self.host_next_at.get(host, 0.0)
        if now < nxt:
            return nxt - now
        return 0.0

    def mark_fetched(self, host: str) -> None:
        self.host_next_at[host] = time.time() + self.per_host_delay

    def pop(self) -> _QItem | None:
        return heapq.heappop(self.q) if self.q else None

    def maybe_enqueue_links(self, base_url: str, links: Iterable[str], seed_host: str, depth: int) -> None:
        if depth >= self.max_depth:
            return
        base = urlparse(base_url)
        now = time.time()
        for href in links:
            try:
                absu = urljoin(base.geturl(), href)
                u = self._canon(absu)
                if not u or u in self.seen:
                    continue
                pu = urlparse(u)
                if pu.netloc != seed_host:
                    continue
                # keep scope narrow: prefer obvious job/career paths
                p = pu.path.lower()
                if not any(h in p for h in ALLOWED_PATH_HINTS):
                    # allow if it links to something that *looks* like a job detail (has id-ish)
                    if not any(tok in p for tok in ("/apply", "-job-", "/job/", "/position/")):
                        continue
                self.seen.add(u)
                prio = self._priority(u)
                heapq.heappush(self.q, _QItem(prio, now, u, depth + 1, seed_host))
            except Exception:
                continue