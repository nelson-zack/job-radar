from __future__ import annotations

from radar.db.session import get_session
from radar.db.models import Job

SIMPLIFY_PREFIX = "https://simplify.jobs/"


def has_direct_counterpart(session, job: Job) -> bool:
    return (
        session.query(Job.id)
        .filter(Job.provider == job.provider)
        .filter(Job.company_id == job.company_id)
        .filter(Job.title == job.title)
        .filter(Job.id != job.id)
        .filter(~Job.url.like(f"{SIMPLIFY_PREFIX}%"))
        .first()
        is not None
    )



def cleanup() -> dict:
    removed = 0
    kept = 0
    with get_session() as session:
        jobs = (
            session.query(Job)
            .filter(Job.provider == "github")
            .filter(Job.url.like(f"{SIMPLIFY_PREFIX}%"))
            .all()
        )

        for job in jobs:
            if has_direct_counterpart(session, job):
                session.delete(job)
                removed += 1
            else:
                kept += 1

        session.commit()

    return {"removed": removed, "kept": kept}


if __name__ == "__main__":
    stats = cleanup()
    print(stats)
