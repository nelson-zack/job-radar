import unittest
from datetime import datetime, timezone

from radar.core.github_dates import infer_posted_at


class StubContext:
    def __init__(self, merge=None, add=None, latest=None):
        self.merge = merge
        self.add = add
        self.latest = latest

    def get_pr_merge_date(self, job_id):
        return self.merge

    def get_commit_add_date(self, job_id):
        return self.add

    def get_latest_touch_date(self, job_id):
        return self.latest


class GithubDateInferenceTests(unittest.TestCase):
    def test_prefers_merge_date(self):
        merge = datetime(2024, 9, 1, tzinfo=timezone.utc)
        ctx = StubContext(merge=merge, add=datetime(2024, 8, 20, tzinfo=timezone.utc))
        result = infer_posted_at("job", ctx)
        self.assertEqual(result, merge.replace(tzinfo=None))

    def test_fallback_to_add_date(self):
        add = datetime(2024, 8, 20, tzinfo=timezone.utc)
        ctx = StubContext(add=add)
        result = infer_posted_at("job", ctx)
        self.assertEqual(result, add.replace(tzinfo=None))

    def test_fallback_to_latest_touch(self):
        latest = datetime(2024, 7, 15)
        ctx = StubContext(latest=latest)
        self.assertEqual(infer_posted_at("job", ctx), latest)

    def test_returns_none_when_no_signal(self):
        ctx = StubContext()
        self.assertIsNone(infer_posted_at("job", ctx))


if __name__ == "__main__":
    unittest.main()
