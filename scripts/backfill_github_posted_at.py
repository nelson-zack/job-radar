"""Backfill missing posted_at values for GitHub-curated jobs."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from radar.db.models import Job
from radar.db.session import get_session
from radar.providers.github_curated import fetch_curated_github_jobs

DEFAULT_SAMPLE_SIZE = 10


@dataclass
class BackfillSummary:
    checked: int
    updated: int
    missing_after: int
    sample: list[dict]
    cutoff_run: str

    def to_dict(self) -> dict:
        return asdict(self)


def backfill_missing_posted_at(*, dry_run: bool = False, sample_size: int = DEFAULT_SAMPLE_SIZE) -> BackfillSummary:
    run_timestamp = datetime.now(timezone.utc).isoformat()
    scrape_jobs = fetch_curated_github_jobs()
    lookup = {
        job.get("external_id"): job
        for job in scrape_jobs
        if job.get("external_id") and job.get("posted_at") is not None
    }

    sample_payload: list[dict] = []
    updated = 0
    missing_after = 0
    checked = 0

    with get_session() as session:
        rows: list[Job] = (
            session.query(Job)
            .filter(Job.provider == "github")
            .filter(Job.posted_at == None)  # noqa: E711
            .order_by(Job.id.asc())
            .all()
        )

        for row in rows:
            checked += 1
            payload = lookup.get(row.external_id)
            if payload and payload.get("posted_at"):
                sample_payload.append(
                    {
                        "id": row.id,
                        "company": row.company.name if row.company else None,
                        "title": row.title,
                        "url": row.url,
                        "assigned_posted_at": payload["posted_at"].isoformat(),
                    }
                )
                if not dry_run:
                    row.posted_at = payload["posted_at"]
                updated += 1
            else:
                missing_after += 1

            if len(sample_payload) >= sample_size:
                sample_payload = sample_payload[:sample_size]

        if not dry_run and updated:
            session.commit()

    return BackfillSummary(
        checked=checked,
        updated=updated,
        missing_after=missing_after,
        sample=sample_payload[:sample_size],
        cutoff_run=run_timestamp,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign fallback posted_at dates to GitHub-curated jobs")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without updating the database")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help="Number of sample rows to include in the summary output",
    )
    args = parser.parse_args()

    summary = backfill_missing_posted_at(dry_run=args.dry_run, sample_size=args.sample_size)
    print(summary.to_dict())


if __name__ == "__main__":
    main()
