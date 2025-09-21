from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol


class GitContext(Protocol):
    def get_pr_merge_date(self, job_id: str) -> Optional[datetime]:
        ...

    def get_commit_add_date(self, job_id: str) -> Optional[datetime]:
        ...

    def get_latest_touch_date(self, job_id: str) -> Optional[datetime]:
        ...


def infer_posted_at(job_key: str, ctx: Optional[GitContext]) -> Optional[datetime]:
    if ctx is None:
        return None

    for getter in (
        ctx.get_pr_merge_date,
        ctx.get_commit_add_date,
        ctx.get_latest_touch_date,
    ):
        try:
            dt = getter(job_key)
        except Exception:
            dt = None
        if isinstance(dt, datetime):
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
    return None


def log_inference_metrics(logger, provider: str, inferred: int, undated: int, total: int) -> None:
    if logger:
        logger.info(
            "github-date provider=%s inferred=%s undated=%s total=%s",
            provider,
            inferred,
            undated,
            total,
        )
