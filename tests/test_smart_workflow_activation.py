"""Ensure opt-in is explicit in every existing worker, with no new clock."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    (".github/workflows/rasd-scheduled.yml", 1),
    (".github/workflows/rasd-schedule-backup.yml", 1),
    (".github/workflows/rasd-cloudflare-dispatch.yml", 2),
)
FLAG = "RASD_SMART_NO_EMPTY_INTERVAL_EMAIL: ${{ vars.RASD_SMART_NO_EMPTY_INTERVAL_EMAIL }}"


class WorkflowFlagScope(unittest.TestCase):
    def test_existing_jobs_only_and_no_hardcoded_activation(self):
        for path, expected in FILES:
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                self.assertEqual(text.count(FLAG), expected)
                self.assertNotIn("RASD_SMART_NO_EMPTY_INTERVAL_EMAIL: 'true'", text)
                self.assertNotIn('RASD_SMART_NO_EMPTY_INTERVAL_EMAIL: "true"', text)
                self.assertIn("rasd-production", text)
                self.assertIn("rasd-scheduled-monitor-private-ledger", text)
                self.assertIn("cancel-in-progress: false", text)

    def test_all_three_include_same_existing_periodic_worker(self):
        for path, _ in FILES:
            self.assertIn(
                "python scheduled_rasd.py --mode interval",
                (ROOT / path).read_text(encoding="utf-8")
            )


if __name__ == "__main__":
    unittest.main()
