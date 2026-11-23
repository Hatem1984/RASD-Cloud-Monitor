"""Prevent a Word-parser release from sending historical nightly reports.

Read-only, NO SEND: clocks are fixed; private credentials, CAS and SMTP are
explicitly denied. All relay routes share the same worker and the same guard.
"""
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import scheduled_rasd as worker


class ExpiredCairoDailyRecovery(unittest.TestCase):
    # Actual merge-review hour in Cairo: 23 Nov 2026 19:45 EET.
    before_due = datetime(2026, 11, 23, 17, 45, tzinfo=timezone.utc)
    next_due_recovery = datetime(2026, 11, 23, 20, 7, tzinfo=timezone.utc)
    four_hours_after_due = datetime(2026, 11, 24, 0, 0, tzinfo=timezone.utc)
    expired_after_due = datetime(2026, 11, 24, 1, 7, tzinfo=timezone.utc)

    def test_correct_cairo_days_and_cutoff(self):
        for instant, target, allowed in [
            (self.before_due, "2026-11-22", False),
            (self.next_due_recovery, "2026-11-23", True),
            (self.four_hours_after_due, "2026-11-23", True),
            (self.expired_after_due, "2026-11-23", False),
        ]:
            with self.subTest(instant=instant):
                self.assertEqual(
                    worker.automatic_daily_recovery_window(instant),
                    (target, allowed))

    def test_main_backup_and_cloudflare_do_not_replay_nov22_at_release_hour(self):
        for cron in (
                worker.HALF_HOUR_CRON,
                worker.BACKUP_HALF_HOUR_CRON,
                worker.CLOUDFLARE_CRON):
            with self.subTest(cron=cron):
                with (
                    patch.dict(os.environ, {
                        "GITHUB_EVENT_NAME": "schedule",
                        "RASD_JOB_CRON": cron,
                    }),
                    patch.object(worker, "require_github_scheduler"),
                    patch.object(worker, "protected_credentials") as creds,
                    patch.object(worker, "send_one_word") as smtp,
                ):
                    status = worker.run_scheduled(
                        "rollup_recovery", self.before_due)
                self.assertEqual(
                    status["status"], "expired_daily_recovery_requires_owner_review")
                self.assertFalse(status["smtp_accepted"])
                self.assertFalse(status["cas_mutated"])
                self.assertFalse(status["private_ledger_read"])
                creds.assert_not_called()
                smtp.assert_not_called()

    def test_first_new_due_nov23_is_still_recoverable(self):
        with (
            patch.dict(os.environ, {
                "GITHUB_EVENT_NAME": "schedule",
                "RASD_JOB_CRON": worker.HALF_HOUR_CRON,
            }),
            patch.object(worker, "require_github_scheduler"),
            patch.object(worker, "protected_credentials",
                         side_effect=RuntimeError("private_boundary_reached")) as creds,
        ):
            with self.assertRaisesRegex(RuntimeError, "private_boundary_reached"):
                worker.run_scheduled("rollup_recovery",
                                     self.next_due_recovery)
        creds.assert_called_once()

    def test_normal_22h_daily_path_is_not_modified(self):
        with (
            patch.dict(os.environ, {
                "GITHUB_EVENT_NAME": "schedule",
                "RASD_JOB_CRON": worker.DAILY_CRON,
            }),
            patch.object(worker, "require_github_scheduler"),
            patch.object(worker, "protected_credentials",
                         side_effect=RuntimeError("daily_boundary_reached")) as creds,
        ):
            with self.assertRaisesRegex(RuntimeError, "daily_boundary_reached"):
                worker.run_scheduled("rollup", datetime(
                    2026, 11, 23, 20, 0, tzinfo=timezone.utc))
        creds.assert_called_once()

    def test_expired_after_next_due_has_no_credentials(self):
        with (
            patch.dict(os.environ, {
                "GITHUB_EVENT_NAME": "schedule",
                "RASD_JOB_CRON": worker.HALF_HOUR_CRON,
            }),
            patch.object(worker, "require_github_scheduler"),
            patch.object(worker, "protected_credentials") as creds,
        ):
            status = worker.run_scheduled("rollup_recovery",
                                          self.expired_after_due)
        self.assertEqual(status["status"],
                         "expired_daily_recovery_requires_owner_review")
        creds.assert_not_called()


if __name__ == "__main__":
    unittest.main()
