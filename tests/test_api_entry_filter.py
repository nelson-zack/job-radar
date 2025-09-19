import os
import sys
import types
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("RADAR_DATABASE_URL", "sqlite:///:memory:")

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


class JobsEndpointEntryFilterTests(unittest.TestCase):
    def setUp(self):
        self.original_flag = os.environ.get("FILTER_ENTRY_EXCLUSIONS")
        os.environ["FILTER_ENTRY_EXCLUSIONS"] = "true"

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

            session.add_all(
                [
                    Job(
                        provider="greenhouse",
                        external_id="1",
                        url="https://example.com/senior",
                        company_id=company.id,
                        title="Senior Software Engineer",
                        location="Remote",
                        is_remote=True,
                        level="senior",
                        description="We need leaders with 5+ years of experience.",
                    ),
                    Job(
                        provider="greenhouse",
                        external_id="2",
                        url="https://example.com/associate",
                        company_id=company.id,
                        title="Associate Software Engineer",
                        location="Remote",
                        is_remote=True,
                        level="junior",
                        description="Great for new grads.",
                    ),
                ]
            )
            session.commit()

        def override_db_session():
            with self.SessionLocal() as session:
                yield session

        self.override = override_db_session
        app.dependency_overrides[db_session] = self.override
        self.client = TestClient(app)

    def tearDown(self):
        if self.original_flag is None:
            os.environ.pop("FILTER_ENTRY_EXCLUSIONS", None)
        else:
            os.environ["FILTER_ENTRY_EXCLUSIONS"] = self.original_flag
        app.dependency_overrides.pop(db_session, None)

    def test_senior_roles_are_filtered_out(self):
        response = self.client.get("/jobs?limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["total"], 1)
        for item in data["items"]:
            self.assertNotIn("senior", item["title"].lower())


if __name__ == "__main__":
    unittest.main()
