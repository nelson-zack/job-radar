import os
import sys
import types
import unittest
from datetime import datetime
from unittest import mock

bs4_stub = types.ModuleType("bs4")
bs4_stub.BeautifulSoup = type("BeautifulSoup", (), {})
element_stub = types.ModuleType("bs4.element")
element_stub.Tag = type("Tag", (), {})
bs4_stub.element = element_stub
sys.modules.setdefault("bs4", bs4_stub)
sys.modules.setdefault("bs4.element", element_stub)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("RADAR_DATABASE_URL", "sqlite:///:memory:")

from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from radar.api.main import app
from radar.api.deps import db_session
from radar.db.models import Base, Company, Job


class BackfillPostedAtTests(unittest.TestCase):
    def setUp(self):
        self.prev_token = os.environ.get("RADAR_ADMIN_TOKEN")
        os.environ["RADAR_ADMIN_TOKEN"] = "secret"
        import radar.api.main as main_module
        main_module.ADMIN_TOKEN = "secret"

        engine = create_engine(
            "sqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.SessionLocal = sessionmaker(bind=engine)

        with self.SessionLocal() as session:
            company = Company(name="Acme", slug="acme")
            session.add(company)
            session.flush()
            session.add(
                Job(
                    provider="github",
                    external_id="abc123",
                    url="https://example.com/job",
                    company_id=company.id,
                    title="New Grad SWE",
                    location="Remote",
                    is_remote=True,
                    level="junior",
                    posted_at=None,
                )
            )
            session.commit()

        @contextmanager
        def override_db_session():
            with self.SessionLocal() as session:
                yield session

        app.dependency_overrides[db_session] = override_db_session

        self.session_patch = mock.patch("radar.api.main.get_session", override_db_session)
        self.session_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        if self.prev_token is None:
            os.environ.pop("RADAR_ADMIN_TOKEN", None)
        else:
            os.environ["RADAR_ADMIN_TOKEN"] = self.prev_token
        app.dependency_overrides.pop(db_session, None)
        self.session_patch.stop()

    def test_backfill_updates_missing_dates(self):
        payload = [
            {
                "external_id": "abc123",
                "posted_at": datetime(2025, 9, 15),
            }
        ]

        with mock.patch(
            "radar.api.main.fetch_curated_github_jobs", return_value=payload
        ):
            resp = self.client.post(
                "/admin/backfill-posted-at", headers={"x-token": "secret"}
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["updated"], 1)
        with self.SessionLocal() as session:
            job = (
                session.query(Job)
                .filter(Job.provider == "github", Job.external_id == "abc123")
                .one()
            )
            self.assertEqual(job.posted_at, datetime(2025, 9, 15))


if __name__ == "__main__":
    unittest.main()
