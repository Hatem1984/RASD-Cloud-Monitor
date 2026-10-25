"""Fail-closed static contract: health observation can NEVER deliver or modify private state."""
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicHealthWorkflowContract(unittest.TestCase):
    def test_isolated_no_send_and_no_secrets(self):
        p = ROOT / ".github/workflows/rasd-original-sources-health-daily.yml"
        y = p.read_text(encoding="utf-8")
        self.assertIn("gate69_source_health_readonly.py", y)
        self.assertIn("28 8 * * *", y)
        self.assertIn("contents: read", y)
        self.assertIn("retention-days: 14", y)
        self.assertIn("branches: [main]", y)
        self.assertIn("\'.github/workflows/rasd-original-sources-health-daily.yml\'", y)
        self.assertIn("rasd-original-sources-redacted-health", y)
        self.assertIn("RASD_SOURCE_HEALTH_HOLD_NO_REPORT_NO_EMAIL", y)
        for forbidden in (
            "secrets.", "RASD_GMAIL", "PRIVATE_LEDGER", "SMTP",
            "wrangler", "deploy", "storage", "r2 bucket", "send_mail",
            "pull_request:", "contents: write",
        ):
            # 'SMTP' and 'PRIVATE_LEDGER' are prohibited by design.
            self.assertNotIn(forbidden, y)

    def test_observer_has_exact_three_source_scope_and_never_approves(self):
        source = (ROOT / "gate69_source_health_readonly.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('SOURCES = frozenset(("hapi", "almasryalyoum", "mped-official"))', source)
        self.assertIn('"production_approved": False', source)
        self.assertIn('"email_sent": False', source)
        self.assertIn('"r2_used": False', source)


if __name__ == "__main__":
    unittest.main()
