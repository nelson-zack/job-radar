# scripts/test_db.py
from __future__ import annotations

from datetime import datetime, timezone

from radar.db.session import get_session
from radar.db.crud import upsert_job, query_jobs


def main() -> None:
    # Example job payload (note: posted_at stored as **naive UTC** per our models)
    job = {
        "external_id": "demo-123",
        "company": "DemoCo",
        "title": "Software Engineer I (New Grad)",
        "provider": "crawler",
        "company_token": "democo",
        "url": "https://careers.example.com/jobs/demo-123",
        "location": "Remote (US)",
        "posted_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "description_html": "<p>Entry-level role, 0–2 years, Python/JS.</p>",
        "skills": ["python", "javascript", "sql"],
        "level": "junior",
    }

    # Use a DB session and pass it into CRUD helpers
    with get_session() as session:
        upsert_job(job_data=job, session=session)

        rows = query_jobs(session=session, limit=5)
        print(f"Fetched {len(rows)} row(s)")
        for r in rows:
            print(r.id, r.company, r.title, r.level, r.url)


if __name__ == "__main__":
    main()