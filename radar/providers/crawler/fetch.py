from __future__ import annotations
import time, random
import requests
from urllib.parse import urlparse
from urllib import robotparser

DEFAULT_UA = "JobRadarCrawler/0.1 (+https://example.com/bot; respectful; contact=you@example.com)"

class Fetcher:
    def __init__(self, timeout: float = 15.0, ua: str = DEFAULT_UA):
        self.timeout = timeout
        self.ua = ua
        self._robots: dict[str, robotparser.RobotFileParser] = {}

    def _get_robots(self, root: str):
        rp = self._robots.get(root)
        if rp:
            return rp
        robots_url = f"{root}/robots.txt"
        rp = robotparser.RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
        except Exception:
            pass
        self._robots[root] = rp
        return rp

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        root = f"{p.scheme}://{p.netloc}"
        rp = self._get_robots(root)
        try:
            # Some type checkers complain about attributes on RobotFileParser;
            # just ask can_fetch() directly and fall back to allowing on any
            # runtime error or unreadable robots.txt.
            return bool(rp.can_fetch(self.ua, url))
        except Exception:
            return True

    def get(self, url: str) -> tuple[int, str, dict]:
        """Return (status, text, headers)."""
        if not self.allowed(url):
            return 999, "", {}
        headers = {"User-Agent": self.ua, "Accept-Encoding": "gzip, deflate"}
        try:
            r = requests.get(url, headers=headers, timeout=self.timeout)
            return r.status_code, r.text or "", dict(r.headers or {})
        except requests.RequestException:
            return 0, "", {}
        finally:
            # random jitter to be extra polite on top of frontier pacing
            time.sleep(random.uniform(0.05, 0.15))