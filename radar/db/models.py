

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
    UniqueConstraint,
    Text,
    Index,
    Integer,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# --- SQLAlchemy base ---------------------------------------------------------

class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


# --- Enums -------------------------------------------------------------------

PROVIDERS = (
    "greenhouse",
    "lever",
    "workday",
    "workable",
    "ashby",
    "crawler",   # generic HTML crawler
    "github",    # curated repos of new‑grad listings
)

LEVELS = ("junior", "mid", "senior", "unknown")


# --- Models ------------------------------------------------------------------

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(300))

    # Optional: where we fetch jobs for this company (for ATS-backed providers)
    ats_provider: Mapped[Optional[str]] = mapped_column(
        Enum(*PROVIDERS, name="provider_enum", native_enum=False), nullable=True
    )
    ats_token: Mapped[Optional[str]] = mapped_column(String(200))

    # Relationships
    jobs: Mapped[list[Job]] = relationship(back_populates="company", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"&lt;Company id={self.id} slug={self.slug!r}&gt;"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        # Prevent duplicates from the same source
        UniqueConstraint("provider", "external_id", name="uq_job_provider_external"),
        Index("ix_jobs_posted_at", "posted_at"),
        Index("ix_jobs_company_posted_at", "company_id", "posted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # External/source identifiers
    provider: Mapped[str] = mapped_column(
        Enum(*PROVIDERS, name="provider_enum", native_enum=False), nullable=False, index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(600), nullable=False)

    # Company link
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    company: Mapped["Company"] = relationship(back_populates="jobs")

    # Core job fields
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(300))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Normalized level signal (set by our heuristics)
    level: Mapped[str] = mapped_column(
        Enum(*LEVELS, name="level_enum", native_enum=False), default="unknown", nullable=False, index=True
    )

    # Dates/content
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Bookkeeping
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Optional extra categorization
    function: Mapped[Optional[str]] = mapped_column(String(80))   # e.g., backend, frontend, security
    seniority_score: Mapped[Optional[int]] = mapped_column(Integer)  # internal scoring/debug

    # Relationships
    skills: Mapped[list["JobSkill"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"&lt;Job id={self.id} prov={self.provider} title={self.title!r}&gt;"


class JobSkill(Base):
    """Stores skill matches per job (what our skill filter computed)."""

    __tablename__ = "job_skills"
    __table_args__ = (UniqueConstraint("job_id", "skill", name="uq_job_skill"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    job: Mapped["Job"] = relationship(back_populates="skills")

    skill: Mapped[str] = mapped_column(String(60), nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # simple weight

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"&lt;JobSkill job_id={self.job_id} skill={self.skill!r} score={self.score}&gt;"


class CrawlRun(Base):
    """Optional: track crawl/fetch sessions for observability."""

    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(
        Enum(*PROVIDERS, name="provider_enum", native_enum=False), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    pages_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"&lt;CrawlRun id={self.id} provider={self.provider} pages={self.pages_fetched}&gt;"


__all__ = [
    "Base",
    "Company",
    "Job",
    "JobSkill",
    "CrawlRun",
    "PROVIDERS",
    "LEVELS",
]