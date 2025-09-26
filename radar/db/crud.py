from typing import Iterable, Optional, Sequence, Tuple, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from radar.db.models import Company, Job, JobSkill


SkillLike = Union[str, Tuple[str, int]]


def _normalize_skill(s: SkillLike) -> Optional[str]:
    """
    Accept either a plain string or a (skill, weight) pair.
    Return only the skill text (weights are ignored at DB layer).
    """
    if not s:
        return None
    if isinstance(s, tuple):
        if not s:
            return None
        # first element is the skill label
        return str(s[0]).strip() or None
    return str(s).strip() or None


def _apply_job_skills(session: Session, job_id: int, skills: Optional[Iterable[SkillLike]]) -> None:
    """
    Replace skills for a job with the provided iterable.
    If skills is None, do nothing (keeps existing values).
    """
    if skills is None:
        return

    # Clear existing skills (cheap single statement)
    session.query(JobSkill).filter(JobSkill.job_id == job_id).delete(synchronize_session=False)

    # Insert new skills
    for raw in skills:
        skill = _normalize_skill(raw)
        if not skill:
            continue
        session.add(JobSkill(job_id=job_id, skill=skill))


def _slugify(text: str) -> str:
    import re
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def get_or_create_company(
    session: Session,
    *,
    name: Optional[str] = None,
    slug: Optional[str] = None,
) -> Optional[Company]:
    """
    Resolve a Company row from (name and/or slug). Creates one if not found.
    Returns None if neither name nor slug is provided.
    """
    if not name and not slug:
        return None

    resolved_slug = slug or (name and _slugify(name)) or None
    stmt = select(Company).where(Company.slug == resolved_slug) if resolved_slug else None
    company: Optional[Company] = None

    if stmt is not None:
        company = session.execute(stmt).scalar_one_or_none()

    if company is None and name:
        # Try by name as a fallback
        company = session.query(Company).filter(Company.name == name).one_or_none()

    if company is None:
        # Create it
        company = Company(name=name or resolved_slug, slug=resolved_slug or _slugify(name or "company"))
        session.add(company)
        session.flush()  # ensure company.id

    return company


def create_job(session: Session, job_data: dict) -> Job:
    """
    Create a Job row. Handles 'company'/'company_slug' and 'skills' in job_data.
    - company/company_slug: resolves/creates Company and sets company_id
    - skills (list[str|tuple[str,int]]): written to job_skills after insert
    """
    # Extract relationship-ish fields
    skills = job_data.pop("skills", None)
    company_name = job_data.pop("company", None)
    company_slug = job_data.pop("company_slug", None)

    # Accept description_html (from scrapers) as description if not provided
    desc_html = job_data.pop("description_html", None)
    if job_data.get("description") is None and desc_html is not None:
        job_data["description"] = desc_html

    # Accept company_token (from providers/CSV) as a slug alias
    company_token = job_data.pop("company_token", None)
    if not company_slug and company_token:
        company_slug = str(company_token).strip() or None

    # Resolve company_id if not already provided
    if not job_data.get("company_id"):
        company = get_or_create_company(session, name=company_name, slug=company_slug)
        if company is not None:
            job_data["company_id"] = company.id

    # Construct and persist the Job
    job = Job(**job_data)
    session.add(job)
    session.flush()  # get job.id

    _apply_job_skills(session, job.id, skills)

    session.commit()
    session.refresh(job)
    return job


def get_job_by_id(session: Session, job_id: int) -> Optional[Job]:
    return session.query(Job).filter(Job.id == job_id).first()


def get_jobs(session: Session, skip: int = 0, limit: int = 100) -> Sequence[Job]:
    return session.query(Job).offset(skip).limit(limit).all()


def delete_job(session: Session, job_id: int) -> bool:
    # Remove skills first to avoid orphans if FK doesn't cascade
    session.query(JobSkill).filter(JobSkill.job_id == job_id).delete(synchronize_session=False)
    job = session.query(Job).filter(Job.id == job_id).first()
    if job:
        session.delete(job)
        session.commit()
        return True
    return False


def upsert_job(session: Session, job_data: dict) -> Job:
    """
    Upsert a job by its external_id (scoped by provider if present).
    Expects job_data to include: external_id, url, title, provider, etc.
    Optional inputs:
      - company (name) and/or company_slug  -> resolves company_id
      - skills: list[str | tuple[str,int]]  -> replaces job_skills
    """
    # Extract extras that shouldn't be passed to the ORM constructor directly
    skills = job_data.pop("skills", None)
    company_name = job_data.pop("company", None)
    company_slug = job_data.pop("company_slug", None)
    legacy_external_id = job_data.pop("legacy_external_id", None)

    # Accept description_html (from scrapers) as description if not provided
    desc_html = job_data.pop("description_html", None)
    if job_data.get("description") is None and desc_html is not None:
        job_data["description"] = desc_html

    # Accept company_token (from providers/CSV) as a slug alias
    company_token = job_data.pop("company_token", None)
    if not company_slug and company_token:
        company_slug = str(company_token).strip() or None

    external_id = job_data.get("external_id")
    if not external_id:
        raise ValueError("upsert_job requires 'external_id' in job_data")

    provider = job_data.get("provider")
    q = session.query(Job).filter(Job.external_id == external_id)
    if provider:
        q = q.filter(Job.provider == provider)
    job = q.one_or_none()

    if job is None and legacy_external_id:
        legacy_q = session.query(Job).filter(Job.external_id == legacy_external_id)
        if provider:
            legacy_q = legacy_q.filter(Job.provider == provider)
        job = legacy_q.one_or_none()
        if job is None:
            # Legacy curated rows may predate provider tagging; retry without provider filter.
            job = (
                session.query(Job)
                .filter(Job.external_id == legacy_external_id)
                .one_or_none()
            )
        if job is not None:
            job.external_id = external_id
            if provider and job.provider != provider:
                job.provider = provider

    # Ensure company_id if not already provided
    if not job_data.get("company_id"):
        company = get_or_create_company(session, name=company_name, slug=company_slug)
        if company is not None:
            job_data["company_id"] = company.id

    if job:
        for key, value in job_data.items():
            if key == "id":
                continue
            if value is None:
                continue
            if key == "posted_at" and getattr(job, "posted_at", None) is not None:
                continue
            setattr(job, key, value)
    else:
        job = Job(**job_data)
        session.add(job)
        session.flush()  # ensure job.id is available

    # Replace skills if provided
    _apply_job_skills(session, job.id, skills)

    session.commit()
    session.refresh(job)
    return job


def query_jobs(session: Session, limit: int = 10) -> Sequence[Job]:
    return session.query(Job).order_by(Job.id.desc()).limit(limit).all()
