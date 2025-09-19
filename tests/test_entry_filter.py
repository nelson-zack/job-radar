import unittest

from radar.filters.entry import filter_entry_level


class EntryFilterTests(unittest.TestCase):
    def test_senior_title_excluded(self):
        decision, _ = filter_entry_level({"title": "Senior Software Engineer"})
        self.assertEqual(decision, "exclude")

    def test_three_plus_years_excluded(self):
        decision, _ = filter_entry_level(
            {
                "title": "Software Engineer (L2)",
                "description": "We need builders with 3+ years of experience.",
            }
        )
        self.assertEqual(decision, "exclude")

    def test_two_plus_years_kept(self):
        decision, _ = filter_entry_level(
            {
                "title": "Software Engineer",
                "description": "Ideal candidate has 2+ years experience.",
            }
        )
        self.assertEqual(decision, "keep")

    def test_associate_kept(self):
        decision, _ = filter_entry_level({"title": "Associate Software Engineer"})
        self.assertEqual(decision, "keep")

    def test_lead_intern_excluded(self):
        decision, _ = filter_entry_level({"title": "Lead Intern"})
        self.assertEqual(decision, "exclude")

    def test_new_grad_kept(self):
        decision, _ = filter_entry_level({"title": "New Grad Software Engineer"})
        self.assertEqual(decision, "keep")


if __name__ == "__main__":
    unittest.main()
