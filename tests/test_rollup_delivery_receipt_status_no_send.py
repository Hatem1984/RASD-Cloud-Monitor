"""Daily report status never conflates a durable reservation with SMTP.

All tests are offline: no Gmail, actual mail, archive, or private ledger I/O.
"""
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import scheduled_rasd as rasd


class RollupReceiptStatusNoSend(unittest.TestCase):
    def run_existing(self, status):
        ledger = MagicMock()
        key = rasd.digest_key("rollup:2026-11-17")
        ledger.read.return_value = (
            {"entries": {key: {"status": status}}}, "sha-fixture")
        with (
            patch.dict(os.environ, {
                "GITHUB_EVENT_NAME": "schedule",
                "RASD_JOB_CRON": rasd.DAILY_CRON,
            }),
            patch.object(rasd, "require_github_scheduler"),
            patch.object(rasd, "scheduled_phase", return_value="rollup"),
            patch.object(rasd, "protected_credentials", return_value=(
                "sender@gmail.com", "approved@example.invalid", "fixture",
                ledger)),
            patch.object(rasd, "news_for_rollup") as news,
            patch.object(rasd, "send_one_word") as smtp,
            patch.object(rasd, "consolidate_sent_words", create=True) as archive,
        ):
            try:
                result = rasd.run_scheduled(
                    "rollup",
                    datetime(2026, 11, 17, 20, 3, tzinfo=timezone.utc))
            except RuntimeError as err:
                result = err
            news.assert_not_called()
            smtp.assert_not_called()
            archive.assert_not_called()
            ledger.reserve.assert_not_called()
            ledger.mark_smtp_accepted.assert_not_called()
        return result

    def test_unconfirmed_reservation_is_not_reported_as_sent(self):
        result = self.run_existing("reserved")
        self.assertEqual(result["status"],
                         "rollup_reserved_pending_manual_reconciliation")
        self.assertFalse(result["smtp_accepted"])
        self.assertFalse(result["inbox_delivery_verified"])
        self.assertTrue(result["manual_reconciliation_required"])

    def test_previous_smtp_acceptance_is_not_inbox_delivery(self):
        result = self.run_existing("smtp_accepted")
        self.assertEqual(result["status"],
                         "rollup_already_smtp_accepted_unconfirmed_inbox")
        self.assertFalse(result["smtp_accepted"])
        self.assertFalse(result["inbox_delivery_verified"])
        self.assertFalse(result["manual_reconciliation_required"])

    def test_existing_manual_hold_is_not_retried(self):
        result = self.run_existing("hold")
        self.assertEqual(result["status"], "rollup_ledger_hold_requires_review")
        self.assertFalse(result["smtp_accepted"])
        self.assertTrue(result["manual_reconciliation_required"])

    def test_untrusted_ledger_status_fails_closed_without_email(self):
        result = self.run_existing("pretend-delivered")
        self.assertIsInstance(result, RuntimeError)
        self.assertEqual(str(result), "daily_rollup_ledger_status_invalid")


if __name__ == "__main__":
    unittest.main()
