import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radar.db.models import Base, Job
from radar.db.crud import upsert_job


class UpsertPostedAtTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_upsert_only_sets_posted_at_when_null(self):
        with self.Session() as session:
            job_data = {
                "provider": "github",
                "external_id": "abc123",
                "url": "https://example.com",
                "title": "New Grad SWE",
                "company": "Example",
            }
            upsert_job(session, job_data.copy())

            first_update = job_data | {"posted_at": datetime(2025, 9, 15)}
            upsert_job(session, first_update)

            second_update = job_data | {"posted_at": datetime(2025, 10, 1)}
            upsert_job(session, second_update)

            job = session.query(Job).filter_by(provider="github", external_id="abc123").one()
            self.assertEqual(job.posted_at, datetime(2025, 9, 15))


if __name__ == "__main__":
    unittest.main()
