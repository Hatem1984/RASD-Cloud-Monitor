"""Release guard: all existing production schedulers suppress empty intervals.

Pure source-contract test. No secrets, network, or email.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RULE = re.compile(
    r"(?m)^[ 	]+RASD_SMART_NO_EMPTY_INTERVAL_EMAIL:[ 	]*'true'[ 	]*(?:#.*)?$"
)
SCHEDULES = {
    ".github/workflows/rasd-scheduled.yml": 1,
    ".github/workflows/rasd-schedule-backup.yml": 1,
    ".github/workflows/rasd-cloudflare-dispatch.yml": 2,
}


class SmartIntervalReleaseConfig(unittest.TestCase):
    def test_each_production_job_opts_in(self):
        for rel, expected in SCHEDULES.items():
            with self.subTest(workflow=rel):
                body = (ROOT / rel).read_text(encoding="utf-8")
                self.assertEqual(
                    len(RULE.findall(body)),
                    expected,
                    "One scheduler missing the no-empty-news release flag",
                )

    def test_both_empty_and_image_hold_paths_are_guarded(self):
        body = (ROOT / "scheduled_rasd.py").read_text(encoding="utf-8")
        guard = 'os.environ.get("RASD_SMART_NO_EMPTY_INTERVAL_EMAIL") == "true"'
        self.assertEqual(body.count(guard), 2)
        self.assertEqual(body.count("return smart_interval_no_mail("), 2)

    def test_review_does_not_modify_daily_timing(self):
        native = (ROOT / ".github/workflows/rasd-scheduled.yml").read_text(encoding="utf-8")
        backup = (ROOT / ".github/workflows/rasd-schedule-backup.yml").read_text(encoding="utf-8")
        self.assertIn("7,18,37,48 * * * *", native)
        self.assertIn("0 19,20 * * *", native)
        self.assertIn("13,43 * * * *", backup)


if __name__ == "__main__":
    unittest.main()
