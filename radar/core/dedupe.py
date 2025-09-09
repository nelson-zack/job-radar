from __future__ import annotations
from typing import Iterable, Dict, List
from .normalize import NormalizedJob

def _fingerprint(job: NormalizedJob) -> str:
    # Deterministic key based on title+company+url (case-insensitive for safety)
    return f"{job.title.lower()}|{job.company.lower()}|{job.url.lower()}"

def deduplicate_jobs(jobs: Iterable[NormalizedJob]) -> list[NormalizedJob]:
    seen: Dict[str, NormalizedJob] = {}
    for j in jobs:
        seen[_fingerprint(j)] = j
    return list(seen.values())
