"""No production RASD reporter may silently drop the authorized second email.
Offline contract test only: no GitHub requests, SMTP, secrets or credentials.
"""
import unittest
from pathlib import Path


class ProductionCcWiring(unittest.TestCase):
    def test_cloudflare_interval_and_daily_pass_authorized_cc(self):
        source = Path(".github/workflows/rasd-cloudflare-dispatch.yml").read_text(encoding="utf-8")
        self.assertIn("protected-cloudflare-interval:", source)
        self.assertIn("protected-cloudflare-cairo-daily:", source)
        self.assertEqual(source.count("RASD_REPORT_TO: ${{ secrets.RASD_REPORT_TO }}"), 2)
        self.assertEqual(source.count("RASD_REPORT_CC: ${{ vars.RASD_REPORT_CC }}"), 2)
        for block in source.split("RASD_REPORT_TO: ${{ secrets.RASD_REPORT_TO }}")[1:]:
            self.assertIn("RASD_REPORT_CC: ${{ vars.RASD_REPORT_CC }}", block[:160])

    def test_backup_and_main_live_scheduler_pass_same_second_recipient(self):
        for path in (".github/workflows/rasd-schedule-backup.yml",
                     ".github/workflows/rasd-scheduled.yml"):
            with self.subTest(path=path):
                source = Path(path).read_text(encoding="utf-8")
                self.assertIn("RASD_REPORT_CC: ${{ vars.RASD_REPORT_CC }}", source)
                self.assertIn("RASD_REPORT_TO: ${{ secrets.RASD_REPORT_TO }}", source)
                self.assertIn("RASD_PRIVATE_LEDGER_TOKEN:", source)

    def test_second_recipient_is_pinned_by_digest_in_delivery_code(self):
        source = Path("scheduled_rasd.py").read_text(encoding="utf-8")
        self.assertIn("APPROVED_REPORT_COPY_SHA256", source)
        self.assertIn("report_copy_recipient_not_approved", source)
        self.assertIn("to_addrs=destinations", source)
        self.assertNotIn("Tarek.soliman1983@gmail.com", source)


if __name__ == "__main__":
    unittest.main()
