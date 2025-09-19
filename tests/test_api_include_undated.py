import os
import sys
import types
import unittest
from datetime import datetime

bs4_stub = types.ModuleType("bs4")
bs4_stub.BeautifulSoup = type("BeautifulSoup", (), {})
element_stub = types.ModuleType("bs4.element")
element_stub.Tag = type("Tag", (), {})
bs4_stub.element = element_stub
sys.modules.setdefault("bs4", bs4_stub)
sys.modules.setdefault("bs4.element", element_stub)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from radar.api.main import app
from radar.api.deps import db_session
from radar.db.models import Base, Company, Job


class IncludeUndatedTests(unittest.TestCase):
    def setUp(self):
        self.original_flag = os.environ.get("GITHUB_DATE_INFERENCE")
        os.environ["GITHUB_DATE_INFERENCE"] = "true"
        os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
        os.environ.setdefault("RADAR_DATABASE_URL", "sqlite:///:memory:")

        engine = create_engine(
            "sqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.SessionLocal = sessionmaker(bind=engine)

        with self.SessionLocal() as session:
            company = Company(name="Beta", slug="beta")
            session.add(company)
            session.flush()

            session.add_all(
                [
                    Job(
                        provider="github",
                        external_id="1",
                        url="https://example.com/undated",
                        company_id=company.id,
                        title="Associate Software Engineer",
                        location="Remote",
                        is_remote=True,
                        level="junior",
                        description="Great for new grads",
                        posted_at=None,
                    ),
                    Job(
                        provider="github",
                        external_id="2",
                        url="https://example.com/dated",
                        company_id=company.id,
                        title="New Grad Software Engineer",
                        location="Remote",
                        is_remote=True,
                        level="junior",
                        description="",
                        posted_at=datetime(2024, 9, 1),
                    ),
                ]
            )
            session.commit()

        def override_db_session():
            with self.SessionLocal() as session:
                yield session

        app.dependency_overrides[db_session] = override_db_session
        self.client = TestClient(app)

    def tearDown(self):
        if self.original_flag is None:
            os.environ.pop("GITHUB_DATE_INFERENCE", None)
        else:
            os.environ["GITHUB_DATE_INFERENCE"] = self.original_flag
        app.dependency_overrides.pop(db_session, None)

    def test_undated_excluded_by_default(self):
        resp = self.client.get("/jobs?limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        for item in data["items"]:
            self.assertIsNotNone(item["posted_at"])

    def test_include_undated_parameter(self):
        resp = self.client.get("/jobs?limit=10&include_undated=true")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 2)
        titles = {item["title"] for item in data["items"]}
        self.assertIn("Associate Software Engineer", titles)


if __name__ == "__main__":
    unittest.main()
