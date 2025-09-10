"""Shared SQLAlchemy session/engine setup for Job Radar.

Usage patterns
--------------
- Import `SessionLocal` and `get_session` for app code / FastAPI deps.
- Import `Base` for model declarations (e.g., class Foo(Base): ...).
- Configure the database URL via env var `RADAR_DATABASE_URL` (preferred)
  or `DATABASE_URL`. Falls back to a local SQLite file for convenience.

Environment variables (optional)
--------------------------------
RADAR_DATABASE_URL / DATABASE_URL:
    e.g. postgresql+psycopg://user:pass@host:5432/dbname

RADAR_DB_POOL_SIZE (int, default 5)
RADAR_DB_MAX_OVERFLOW (int, default 10)
RADAR_DB_ECHO ("1" to enable SQL echo)

RADAR_DOTENV (path to .env, default ".env")
    If `python-dotenv` is installed, this module will auto‑load environment
    variables from this file on import. This helps keep CLI and API processes
    pointed at the same database without extra flags.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

# Optional: load environment variables from a .env file if available
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None  # type: ignore

if load_dotenv is not None:
    # Allow override of the .env path via RADAR_DOTENV; default to project root .env
    _ = load_dotenv(dotenv_path=os.getenv("RADAR_DOTENV", ".env"))


# --- Declarative base for all ORM models ---
class Base(DeclarativeBase):
    pass


def _coalesce_url() -> str:
    url = (
        os.getenv("RADAR_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or "sqlite:///./radar.db"
    )
    # Normalize legacy PostgreSQL scheme if present
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    # Prefer psycopg v3 driver if a bare postgresql:// URL is provided
    if url.startswith("postgresql://") and "+" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def make_engine(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine with sensible defaults.

    - pool_pre_ping avoids stale connections
    - echo can be toggled via RADAR_DB_ECHO
    - pool sizing via RADAR_DB_POOL_SIZE / RADAR_DB_MAX_OVERFLOW
    """
    url = url or _coalesce_url()

    pool_size = int(os.getenv("RADAR_DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("RADAR_DB_MAX_OVERFLOW", "10"))
    echo = os.getenv("RADAR_DB_ECHO", "0") == "1"

    # SQLite does not use pool sizing the same way; keep kwargs minimal.
    if url.startswith("sqlite"):
        engine = create_engine(url, echo=echo, pool_pre_ping=True)
    else:
        engine = create_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )
    return engine


# Module‑level engine & session factory (import cost is low)
ENGINE: Engine = make_engine()
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context manager that yields a DB session and ensures cleanup.

    Example:
        with get_session() as db:
            db.add(obj)
            db.commit()

    In FastAPI, you can wrap this as a dependency:

        def get_db():
            with get_session() as db:
                yield db
    """
    session: Session = SessionLocal()
    try:
        yield session
        # Do not auto-commit; callers should commit explicitly
    finally:
        session.close()


def current_engine_url() -> str:
    """Return the effective SQLAlchemy URL for debugging/logging."""
    try:
        return str(ENGINE.url)
    except Exception:
        return "<unavailable>"


def test_connection() -> bool:
    """Lightweight connectivity check. Returns True on success."""
    try:
        with ENGINE.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False