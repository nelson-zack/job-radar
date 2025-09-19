import os
import sys
import types
import unittest
from datetime import datetime
from unittest import mock

bs4_stub = types.ModuleType("bs4")
bs4_stub.BeautifulSoup = type("BeautifulSoup", (), {})
bs4_element = types.ModuleType("bs4.element")
bs4_element.Tag = type("Tag", (), {})
bs4_stub.element = bs4_element
sys.modules.setdefault("bs4", bs4_stub)
sys.modules.setdefault("bs4.element", bs4_element)

import radar.api.main as main_module
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from radar.api.main import app
from radar.api.deps import db_session
from radar.db.models import Base, Company, Job


class ProviderVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.prev_flag = main_module.ENABLE_EXPERIMENTAL
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
            company = Company(name="Acme", slug="acme")
            session.add(company)
            session.flush()

            greenhouse = Job(
                provider="greenhouse",
                external_id="g1",
                url="https://example.com/g1",
                company_id=company.id,
                title="New Grad SWE",
                location="Remote",
                is_remote=True,
                level="junior",
                posted_at=datetime(2025, 9, 1)
            )
            ashby = Job(
                provider="ashby",
                external_id="a1",
                url="https://example.com/a1",
                company_id=company.id,
                title="New Grad Dev",
                location="Remote",
                is_remote=True,
                level="junior",
                posted_at=datetime(2025, 9, 2)
            )
            session.add_all([greenhouse, ashby])
            session.commit()
            self.greenhouse_id = greenhouse.id
            self.ashby_id = ashby.id

        def override_db_session():
            with self.SessionLocal() as session:
                yield session

        app.dependency_overrides[db_session] = override_db_session
        self.session_patch = mock.patch('radar.api.main.get_session', override_db_session)
        self.session_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        main_module.ENABLE_EXPERIMENTAL = self.prev_flag
        app.dependency_overrides.pop(db_session, None)
        self.session_patch.stop()

    def test_default_hides_experimental(self):
        main_module.ENABLE_EXPERIMENTAL = False

        resp = self.client.get('/jobs?limit=10')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total'], 1)
        ids = {item['id'] for item in data['items']}
        self.assertIn(self.greenhouse_id, ids)
        self.assertNotIn(self.ashby_id, ids)

    def test_enable_experimental_includes_all(self):
        main_module.ENABLE_EXPERIMENTAL = True

        resp = self.client.get('/jobs?limit=10')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ids = {item['id'] for item in data['items']}
        self.assertIn(self.greenhouse_id, ids)
        self.assertIn(self.ashby_id, ids)

    def test_explicit_provider_bypasses_flag(self):
        main_module.ENABLE_EXPERIMENTAL = False

        resp = self.client.get('/jobs?provider=ashby')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['items'][0]['id'], self.ashby_id)


if __name__ == '__main__':
    unittest.main()
