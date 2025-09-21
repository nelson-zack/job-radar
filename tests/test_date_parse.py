import unittest
from datetime import datetime

from radar.core.date_parse import parse_curated_date


class CuratedDateParseTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2025, 9, 18, 15, 30, 0)

    def test_month_day_parsing(self):
        dt = parse_curated_date("Sep 17", now=self.now)
        self.assertEqual(dt, datetime(2025, 9, 17))

    def test_iso_date(self):
        dt = parse_curated_date("2025-09-14", now=self.now)
        self.assertEqual(dt, datetime(2025, 9, 14))

    def test_relative_days(self):
        dt = parse_curated_date("3 days ago", now=self.now)
        self.assertEqual(dt, datetime(2025, 9, 15))

    def test_short_days(self):
        dt = parse_curated_date("1d", now=self.now)
        self.assertEqual(dt, datetime(2025, 9, 17))

    def test_hours_round_down(self):
        dt = parse_curated_date("12h", now=self.now)
        self.assertEqual(dt, datetime(2025, 9, 18))

    def test_invalid_returns_none(self):
        self.assertIsNone(parse_curated_date("n/a", now=self.now))


if __name__ == "__main__":
    unittest.main()
