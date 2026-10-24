"""Retire expired Oct22 schedules; preserve the owner's active newsroom."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ExpiredOneOffScheduleCleanup(unittest.TestCase):
    def test_no_expired_october22_oneoff_cron_remains(self):
        nine=(ROOT/".github/workflows/rasd-nine-pm-official-oneoff.yml").read_text("utf-8")
        official=(ROOT/".github/workflows/rasd-official-daily.yml").read_text("utf-8")
        for doc in (nine,official):
            self.assertNotIn("cron: '0 18 22 10 *'",doc)
            self.assertNotIn("cron: '0 19 22 10 *'",doc)
            self.assertNotIn("cron: '30 19 22 10 *'",doc)
            self.assertNotIn("cron: '0 20 22 10 *'",doc)
        self.assertNotIn("  schedule:",nine)
        self.assertIn("vars.RASD_OFFICIAL_AUTOMATION_ENABLED == 'true'",official)
        self.assertNotIn("      - main\n",official.split("  workflow_dispatch:",1)[0])

    def test_active_protected_newsroom_cron_remains_owner_approved(self):
        newsroom=(ROOT/".github/workflows/rasd-scheduled.yml").read_text("utf-8")
        self.assertIn("cron: '7,18,37,48 * * * *'",newsroom)
        self.assertIn("RASD_AUTOMATION_ENABLED: 'true'",newsroom)
        self.assertIn("environment: rasd-production",newsroom)
        self.assertIn("vars.RASD_AUTOMATION_PAUSED != 'true'",newsroom)
        self.assertNotIn("railway",newsroom.lower())

    def test_readme_distinguishes_official_inbox_from_future_newsroom_schedule(self):
        text=(ROOT/"README.md").read_text("utf-8").splitlines()[2]
        self.assertIn("أول تشغيل Cron تلقائي لم يثبت",text)
        self.assertIn("Inbox",text)
        self.assertIn("100%",text)

if __name__=="__main__":
    unittest.main()
