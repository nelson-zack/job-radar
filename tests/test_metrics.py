import os
import sys
import types
import unittest
from datetime import datetime
from unittest import mock
from contextlib import contextmanager

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


class MetricsEndpointTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
        os.environ.setdefault("RADAR_DATABASE_URL", "sqlite:///:memory:")
        os.environ["RADAR_ADMIN_TOKEN"] = "secret"
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

            session.add_all(
                [
                    Job(
                        provider="greenhouse",
                        external_id="g1",
                        url="https://example.com/g1",
                        company_id=company.id,
                        title="Junior Engineer",
                        location="Remote",
                        is_remote=True,
                        level="junior",
                        posted_at=datetime(2025, 9, 1)
                    ),
                    Job(
                        provider="ashby",
                        external_id="a1",
                        url="https://example.com/a1",
                        company_id=company.id,
                        title="Senior Engineer",
                        location="Remote",
                        is_remote=True,
                        level="senior",
                        description="Looking for engineers with 4+ years experience.",
                        posted_at=None
                    ),
                    Job(
                        provider="lever",
                        external_id="l1",
                        url="https://example.com/l1",
                        company_id=company.id,
                        title="Software Engineer",
                        location="Remote",
                        is_remote=True,
                        level="junior",
                        description="Need 3+ years of professional experience.",
                        posted_at=None
                    )
                ]
            )
            session.commit()

        def override_db_session():
            with self.SessionLocal() as session:
                yield session

        @contextmanager
        def override_get_session():
            with self.SessionLocal() as session:
                yield session

        app.dependency_overrides[db_session] = override_db_session
        self.session_patch = mock.patch('radar.api.main.get_session', override_get_session)
        self.session_patch.start()

        self.prev_metrics_flag = main_module.METRICS_PUBLIC
        self.prev_last_ingest = main_module.LAST_INGEST_AT
        main_module.METRICS_PUBLIC = True
        main_module.LAST_INGEST_AT = None
        self.client = TestClient(app)

    def tearDown(self):
        main_module.METRICS_PUBLIC = self.prev_metrics_flag
        main_module.LAST_INGEST_AT = self.prev_last_ingest
        app.dependency_overrides.pop(db_session, None)
        self.session_patch.stop()

    def test_metrics_endpoint_returns_counts(self):
        resp = self.client.get('/metrics/ingestion')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['kept'], 3)
        self.assertEqual(data['excluded_by_title'], 1)
        self.assertEqual(data['excluded_by_yoe'], 1)
        self.assertAlmostEqual(data['percent_undated'], (2 / 3) * 100)
        self.assertIsNone(data['last_ingest_at'])

        expected_by_provider = {
            'greenhouse': {'total': 1, 'undated': 0},
            'ashby': {'total': 1, 'undated': 1},
            'lever': {'total': 1, 'undated': 1},
        }

        self.assertEqual(data['by_provider'], expected_by_provider)

        for provider, stats in data['by_provider'].items():
            self.assertIsInstance(provider, str)
            self.assertIsInstance(stats, dict)
            self.assertIn('total', stats)
            self.assertIn('undated', stats)
            self.assertIsInstance(stats['total'], int)
            self.assertIsInstance(stats['undated'], int)

        self.assertIsInstance(data['total'], int)
        self.assertIsInstance(data['kept'], int)
        self.assertIsInstance(data['excluded_by_title'], int)
        self.assertIsInstance(data['excluded_by_yoe'], int)
        self.assertIsInstance(data['percent_undated'], float)
        self.assertIsInstance(data['by_provider'], dict)

    def test_metrics_requires_token_when_private(self):
        main_module.METRICS_PUBLIC = False
        resp = self.client.get('/metrics/ingestion')
        self.assertEqual(resp.status_code, 401)
        resp = self.client.get('/metrics/ingestion', headers={'x-token': 'secret'})
        self.assertEqual(resp.status_code, 200)

    def test_last_ingest_updates_after_ingest(self):
        with mock.patch('radar.api.main.fetch_curated_github_jobs', return_value=[]):
            resp = self.client.post('/ingest/curated', headers={'x-token': 'secret'})
        self.assertEqual(resp.status_code, 200)
        metrics_resp = self.client.get('/metrics/ingestion')
        self.assertIsNotNone(metrics_resp.json()['last_ingest_at'])


if __name__ == '__main__':
    unittest.main()
