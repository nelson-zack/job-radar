"""Prune stale Job rows based on a configurable retention window.

Defaults to deleting active jobs older than JOB_RETENTION_DAYS (30 days) and
falls back to updated_at for rows without a posted_at timestamp. Designed to be
run from GitHub Actions or a cronjob.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, or_

from radar.db.session import get_session
from radar.db.models import Job

DEFAULT_RETENTION_DAYS = 30
DEFAULT_SAMPLE_SIZE = 10


def _parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class PruneSummary:
    cutoff_utc: str
    matched: int
    deleted: int
    provider: Optional[str]
    dry_run: bool
    sample: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def prune_jobs(
    days: int,
    *,
    provider: Optional[str] = None,
    dry_run: bool = False,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> PruneSummary:
    if days <= 0:
        raise ValueError("Retention 'days' must be positive")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    with get_session() as session:
        query = session.query(Job).filter(Job.active.is_(True))

        if provider:
            query = query.filter(Job.provider == provider)

        stale_clause = or_(
            and_(Job.posted_at.isnot(None), Job.posted_at < cutoff),
            and_(Job.posted_at.is_(None), Job.updated_at < cutoff),
        )
        query = query.filter(stale_clause)

        total = query.count()

        sample_rows = (
            query.order_by(Job.posted_at.asc().nullsfirst(), Job.id.asc())
            .limit(sample_size)
            .all()
        ) if total else []

        sample_payload: list[dict] = [
            {
                "id": row.id,
                "provider": row.provider,
                "company": (row.company.name if row.company else None),
                "title": row.title,
                "posted_at": row.posted_at.isoformat() if row.posted_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "url": row.url,
            }
            for row in sample_rows
        ]

        deleted = 0
        if total and not dry_run:
            deleted = query.delete(synchronize_session=False)
            session.commit()

        summary = PruneSummary(
            cutoff_utc=cutoff.isoformat(),
            matched=total,
            deleted=deleted,
            provider=provider,
            dry_run=dry_run,
            sample=sample_payload,
        )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Prune stale job rows from the database")
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("JOB_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)),
        help="Retention window in days (default: env JOB_RETENTION_DAYS or 30)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=os.getenv("JOB_RETENTION_PROVIDER"),
        help="Optional provider to scope pruning (default: all providers)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=_parse_bool(os.getenv("JOB_RETENTION_DRY_RUN")),
        help="Report what would be deleted without modifying the database",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=int(os.getenv("JOB_RETENTION_SAMPLE", DEFAULT_SAMPLE_SIZE)),
        help="How many representative rows to include in the summary output",
    )

    args = parser.parse_args()

    summary = prune_jobs(
        args.days,
        provider=args.provider,
        dry_run=args.dry_run,
        sample_size=args.sample_size,
    )

    print(summary.to_dict())


if __name__ == "__main__":
    main()
