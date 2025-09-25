# scripts/ingest_github_curated.py
from __future__ import annotations
from radar.providers.github_curated import fetch_curated_github_jobs
from radar.db.session import get_session
from radar.db.crud import upsert_job

def main() -> None:
    rows = fetch_curated_github_jobs()  # only_remote, us_only defaults
    print(f"Fetched {len(rows)} curated jobs")
    saved = 0
    with get_session() as s:
        for r in rows:
            upsert_job(job_data=r, session=s)
            saved += 1
    print(f"Upserted {saved} curated jobs")

if __name__ == "__main__":
    main()