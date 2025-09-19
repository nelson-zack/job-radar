from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, Optional, List
from typing import cast

from fastapi import FastAPI, Depends, Query, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, or_, and_
from sqlalchemy import select, exists
from sqlalchemy.orm import Session
import os
import subprocess, sys
from radar.providers.github_curated import fetch_curated_github_jobs
from radar.db.crud import upsert_job
from radar.db.session import get_session
from radar.core.providers import visible_providers
import logging

ADMIN_TOKEN = os.getenv("RADAR_ADMIN_TOKEN", "")

def require_admin(x_token: str | None) -> None:
    if not ADMIN_TOKEN or x_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


from radar.api.deps import db_session
from radar.db.models import Job, Company, JobSkill
from radar.filters.entry import (
    is_entry_exclusion_enabled,
    filter_entry_level,
    title_exclusion_terms,
    description_exclusion_patterns,
)


def github_date_inference_enabled() -> bool:
    return os.getenv("GITHUB_DATE_INFERENCE", "false").lower() == "true"


# -------------------------
# FastAPI setup
# -------------------------
app = FastAPI(title="Job Radar API", version="0.2.0")
LOGGER = logging.getLogger(__name__)
ENABLE_EXPERIMENTAL = os.getenv("ENABLE_EXPERIMENTAL", "false").lower() == "true"

# CORS (open for now; tighten before public deploy)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Pydantic response models
# -------------------------
class JobOut(BaseModel):
    id: int
    company: Optional[str]
    company_name: Optional[str]
    title: str
    level: str
    is_remote: bool
    posted_at: Optional[datetime]
    url: str

    class Config:
        from_attributes = True  # pydantic v2


class JobsResponse(BaseModel):
    items: List[JobOut]
    total: int
    limit: int
    offset: int


class CompanyOut(BaseModel):
    company: str
    slug: str
    jobs: int


class JobDetailOut(JobOut):
    description: Optional[str] = None
    skills: List[str] = []


# -------------------------
# Routes
# -------------------------
@app.get("/", tags=["meta"])  # small friendly root
async def root():
    return {"message": "Job Radar API is running"}


@app.get("/healthz", tags=["meta"])  # k8s/Render probes
async def healthz():
    return {"status": "ok"}


OrderBy = Literal["posted_at_desc", "posted_at_asc", "id_desc", "id_asc"]


@app.get("/jobs", response_model=JobsResponse, tags=["data"])
async def get_jobs(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    level: Optional[str] = Query(None, description="Filter by inferred level: junior|mid|senior|unknown"),
    remote: Optional[bool] = Query(None, description="is_remote flag"),
    provider: Optional[str] = Query(None, description="Source provider (e.g., greenhouse)"),
    company: Optional[str] = Query(None, description="Company slug"),
    q: Optional[str] = Query(None, description="Substring match on title/company"),
    days: Optional[int] = Query(None, description="Only include jobs posted within the last N days"),
    order: OrderBy = Query("posted_at_desc"),
    skills_any: Optional[str] = Query(None, description="Comma-separated list of skills; match any"),
    us_remote_only: Optional[bool] = Query(None, description="If true, only remote jobs suitable for US"),
    session: Session = Depends(db_session),
):
    """Query jobs with common filters & pagination.

    NOTE: we only return a compact projection; detailed views can come later.
    """
    # Base query with join so we can filter/return company fields
    query = session.query(Job).join(Company, Job.company_id == Company.id)

    # Skills filter (match any) — use EXISTS to avoid join-duplication
    if skills_any:
        skills_list = [s.strip().lower() for s in skills_any.split(",") if s.strip()]
        if skills_list:
            subq = (
                session.query(JobSkill.id)
                .filter(JobSkill.job_id == Job.id)
                .filter(func.lower(JobSkill.skill).in_(skills_list))
            )
            query = query.filter(subq.exists())

    # US-remote helper: for now, treat as simply remote==True
    if us_remote_only:
        query = query.filter(Job.is_remote.is_(True))

    if level:
        query = query.filter(Job.level == level)
    if remote is not None:
        query = query.filter(Job.is_remote.is_(remote))
    if provider and provider.lower() == 'all':
        provider = None
    if provider:
        query = query.filter(Job.provider == provider)
    else:
        allowed = visible_providers(ENABLE_EXPERIMENTAL)
        query = query.filter(Job.provider.in_(allowed))
    if company:
        query = query.filter(Company.slug == company)
    if days is not None and days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Job.posted_at != None).filter(Job.posted_at >= cutoff)  # noqa: E711
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Job.title.ilike(like), Company.name.ilike(like)))

    # Ordering
    if order == "posted_at_desc":
        query = query.order_by(Job.posted_at.desc().nullslast(), Job.id.desc())
    elif order == "posted_at_asc":
        query = query.order_by(Job.posted_at.asc().nullsfirst(), Job.id.asc())
    elif order == "id_asc":
        query = query.order_by(Job.id.asc())
    else:  # id_desc
        query = query.order_by(Job.id.desc())

    entry_filter_enabled = is_entry_exclusion_enabled()

    if entry_filter_enabled:
        query = _apply_entry_sql_filters(query)
        rows, total = _fetch_with_entry_filter(query, offset, limit)
    else:
        total = query.count()
        rows: list[Job] = query.offset(offset).limit(limit).all()

    items: list[JobOut] = [
        JobOut(
            id=j.id,
            company=j.company.slug if j.company else None,
            company_name=j.company.name if j.company else None,
            title=j.title,
            level=j.level,
            is_remote=j.is_remote,
            posted_at=j.posted_at,
            url=j.url,
        )
        for j in rows
    ]

    return JobsResponse(items=items, total=total, limit=limit, offset=offset)


def _apply_entry_sql_filters(query):
    title_lower = func.lower(Job.title)
    for term in title_exclusion_terms():
        pattern = f"%{term}%"
        query = query.filter(~title_lower.like(pattern))

    desc_col = func.lower(func.coalesce(Job.description, ""))
    for pattern in description_exclusion_patterns():
        query = query.filter(~desc_col.like(pattern))

    return query


def _fetch_with_entry_filter(query, offset: int, limit: int):
    chunk_size = max(limit * 3, 100)
    start = 0
    kept_rows: list[Job] = []
    kept_total = 0
    excluded = 0

    while True:
        chunk = query.offset(start).limit(chunk_size).all()
        if not chunk:
            break

        for row in chunk:
            decision, _ = filter_entry_level({
                "title": row.title,
                "description": row.description,
                "description_snippet": getattr(row, "description", None),
            })
            if decision == "exclude":
                excluded += 1
                continue
            kept_total += 1
            if kept_total > offset and len(kept_rows) < limit:
                kept_rows.append(row)

        if kept_total >= offset + limit and len(kept_rows) >= limit:
            break
        if len(chunk) < chunk_size:
            break
        start += chunk_size

    if excluded and LOGGER.isEnabledFor(logging.DEBUG):
        LOGGER.debug(
            "entry-filter api excluded=%s kept=%s offset=%s limit=%s",
            excluded,
            kept_total,
            offset,
            limit,
        )

    return kept_rows, kept_total


@app.get("/companies", response_model=List[CompanyOut], tags=["data"])
async def get_companies(session: Session = Depends(db_session)):
    results = (
        session.query(
            Company.name.label("company"),
            Company.slug.label("slug"),
            func.count(Job.id).label("jobs"),
        )
        .join(Job, Job.company_id == Company.id)
        .group_by(Company.id)
        .order_by(func.count(Job.id).desc())
        .all()
    )
    return [CompanyOut(company=company, slug=slug, jobs=jobs) for company, slug, jobs in results]


@app.get("/jobs/{job_id}", response_model=JobDetailOut, tags=["data"])
async def get_job_detail(job_id: int, session: Session = Depends(db_session)):
    j: Job | None = (
        session.query(Job)
               .join(Company, Job.company_id == Company.id)
               .filter(Job.id == job_id)
               .first()
    )
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")

    # Collect skills
    skills = [row[0] for row in session.query(JobSkill.skill).filter(JobSkill.job_id == j.id).all()]

    return JobDetailOut(
        id=j.id,
        company=j.company.slug if j.company else None,
        company_name=j.company.name if j.company else None,
        title=j.title,
        level=j.level,
        is_remote=j.is_remote,
        posted_at=j.posted_at,
        url=j.url,
        description=j.description,
        skills=skills,
    )


@app.post("/ingest/curated", tags=["admin"])
def ingest_curated(x_token: str | None = Header(default=None)):
    require_admin(x_token)
    rows = fetch_curated_github_jobs()
    saved = 0
    with get_session() as s:
        session_obj: Session = cast(Session, s)
        for r in rows:
            upsert_job(job_data=r, session=session_obj)
            saved += 1
    return {"source": "github_curated", "fetched": len(rows), "saved": saved}


@app.post("/scan/ats", tags=["admin"])
def scan_ats(x_token: str | None = Header(default=None)):
    require_admin(x_token)
    # Run the existing CLI using the current Python interpreter so we stay in this venv.
    script_path = os.path.join(os.getcwd(), "job_radar.py")
    try:
        proc = subprocess.run(
            [sys.executable, script_path, "companies.json", "--profile", "apply-now", "--save"],
            check=True,
            capture_output=True,
            text=True,
        )
        # Return only a tail of stdout to avoid huge payloads
        tail = proc.stdout[-2000:]
        return {"status": "ok", "stdout_tail": tail}
    except subprocess.CalledProcessError as e:
        err_tail = (e.stderr or "")[-1000:]
        raise HTTPException(status_code=500, detail=f"job_radar failed: {err_tail}")


# Optional: tiny debug endpoint to sanity-check DB wiring (non-sensitive)
@app.get("/debug/db", tags=["meta"])  # remove or protect in prod
async def debug_db(session: Session = Depends(db_session)):
    try:
        session.execute(func.now())
        return {"ok": True}
    except Exception as e:  # pragma: no cover
        return {"ok": False, "error": str(e)}


@app.post("/admin/backfill-posted-at", tags=["admin"])
def backfill_posted_at(x_token: str | None = Header(default=None)):
    require_admin(x_token)

    scrape_jobs = fetch_curated_github_jobs(
        enable_scrape=True,
        enable_inference=github_date_inference_enabled(),
    )
    lookup = {
        job.get("external_id"): job
        for job in scrape_jobs
        if job.get("external_id") and job.get("posted_at") is not None
    }

    updated = 0
    missing = 0
    total = 0

    with get_session() as session:
        rows: list[Job] = (
            session.query(Job)
            .filter(Job.provider == "github")
            .filter(Job.posted_at == None)  # noqa: E711
            .all()
        )

        for row in rows:
            total += 1
            scraped = lookup.get(row.external_id)
            if scraped and scraped.get("posted_at"):
                row.posted_at = scraped["posted_at"]
                updated += 1
            else:
                missing += 1

        session.commit()

    return {
        "provider": "github",
        "checked": total,
        "updated": updated,
        "missing": missing,
    }
