from __future__ import annotations
from typing import Callable, Optional, Dict
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Domain → custom extractor(html, url) -> dict or None
_EXTRACTORS: Dict[str, Callable[[str, str], dict | None]] = {}

def register(domain: str, extractor: Callable[[str, str], dict | None]) -> None:
    _EXTRACTORS[domain.lower()] = extractor

def get_extractor_for(url: str):
    host = urlparse(url).netloc.lower()
    return _EXTRACTORS.get(host)

# Example adapter placeholder:
# def _example_adapter(html: str, url: str):
#     soup = BeautifulSoup(html, "lxml")
#     # ... site-specific scraping logic ...
#     return {"title": "...", ...}
# register("jobs.example.com", _example_adapter)