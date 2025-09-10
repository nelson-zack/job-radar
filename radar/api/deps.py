

from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from radar.db.session import get_session


def db_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy :class:`Session`.

    Usage in route handlers:
        def handler(session: Session = Depends(db_session)):
            ...
    """
    with get_session() as session:
        yield session


__all__ = ["db_session"]