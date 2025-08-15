
import os
import json
from typing import List, Dict
from models import Job

def deduplicate_jobs(jobs: List[Job]) -> List[Job]:
    seen = set()
    unique_jobs = []
    for job in jobs:
        identifier = (job.title.lower(), job.company.lower(), job.url)
        if identifier not in seen:
            seen.add(identifier)
            unique_jobs.append(job)
    return unique_jobs

def filter_by_company(jobs: List[Job], allowed_companies: List[str]) -> List[Job]:
    allowed_set = set(name.lower() for name in allowed_companies)
    return [job for job in jobs if job.company.lower() in allowed_set]


# Loads a list of companies from a JSON file.
def load_companies(path: str = "companies.json") -> List[Dict]:
    if not os.path.exists(path):
        print(f"❌ Error: {path} not found.")
        return []
    with open(path, "r") as f:
        return json.load(f)