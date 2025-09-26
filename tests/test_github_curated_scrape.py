import os
import unittest
from datetime import UTC, datetime
from unittest import mock

from radar.providers.github_curated import fetch_curated_github_jobs

SAMPLE_MD_NO_DATE = """| Company | Role | Location | Date | Apply |\n| --- | --- | --- | --- | --- |\n| ExampleCo | New Grad SWE | Remote - US |  | [Apply](https://example.com) |\n"""

SAMPLE_MD = """| Company | Role | Location | Date | Apply |\n| --- | --- | --- | --- | --- |\n| ExampleCo | New Grad SWE | Remote - US | 2025-09-15 | [Apply](https://example.com) |\n"""


class GithubCuratedScrapeTests(unittest.TestCase):
    def setUp(self):
        self.prev_scrape = os.environ.get("GITHUB_CURATED_DATE_SCRAPE")
        self.prev_infer = os.environ.get("GITHUB_DATE_INFERENCE")
        os.environ["GITHUB_CURATED_DATE_SCRAPE"] = "true"
        os.environ["GITHUB_DATE_INFERENCE"] = "false"

    def tearDown(self):
        if self.prev_scrape is None:
            os.environ.pop("GITHUB_CURATED_DATE_SCRAPE", None)
        else:
            os.environ["GITHUB_CURATED_DATE_SCRAPE"] = self.prev_scrape
        if self.prev_infer is None:
            os.environ.pop("GITHUB_DATE_INFERENCE", None)
        else:
            os.environ["GITHUB_DATE_INFERENCE"] = self.prev_infer

    def test_posted_at_scraped_from_markdown(self):
        with mock.patch(
            "radar.providers.github_curated._fetch_markdown", return_value=SAMPLE_MD
        ):
            jobs = fetch_curated_github_jobs(
                sources=["dummy"],
                only_remote=False,
                us_only=False,
                git_ctx=None,
                enable_scrape=True,
                enable_inference=False,
            )
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertIn("posted_at", job)
        self.assertEqual(job["posted_at"], datetime(2025, 9, 15))


    def test_fallback_assigns_current_date_when_missing(self):
        fixed_now = datetime(2025, 9, 30)
        with mock.patch('radar.providers.github_curated._fetch_markdown', return_value=SAMPLE_MD_NO_DATE):
            with mock.patch('radar.providers.github_curated.datetime', wraps=datetime) as dt_mock:
                dt_mock.now.return_value = fixed_now.replace(tzinfo=UTC)
                jobs = fetch_curated_github_jobs(
                    sources=['dummy'],
                    only_remote=False,
                    us_only=False,
                    git_ctx=None,
                    enable_scrape=True,
                    enable_inference=False,
                )
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertIn('posted_at', job)
        self.assertEqual(job['posted_at'], fixed_now.replace(hour=0, minute=0, second=0, microsecond=0))



if __name__ == "__main__":
    unittest.main()
