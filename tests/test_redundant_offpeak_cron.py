"""Off-peak GitHub cron backup acceptance; pure offline no SMTP or external repos."""
from datetime import datetime, timezone
import os
import unittest
from unittest.mock import MagicMock, patch

import scheduled_rasd as worker


class RedundantOffpeakCron(unittest.TestCase):
    def setUp(self):
        # Only this offline fixture emulates a genuinely scheduled worker.
        # Production event authentication remains strictly fail-closed.
        self._scheduled_env = patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule"})
        self._scheduled_env.start()
        self.addCleanup(self._scheduled_env.stop)

    def test_two_chances_per_halfhour_both_share_utc_slot_and_recovery_key(self):
        self.assertEqual(worker.HALF_HOUR_CRON, "7,18,37,48 * * * *")
        for minute in (7, 18):
            t = datetime(2026, 10, 24, 9, minute, tzinfo=timezone.utc)
            self.assertEqual(worker.cairo_window(t)[0], "2026-10-24T09:00Z")
            self.assertEqual(worker.scheduled_phase(worker.HALF_HOUR_CRON, t),
                             "interval")
        for minute in (37, 48):
            t = datetime(2026, 10, 24, 9, minute, tzinfo=timezone.utc)
            self.assertEqual(worker.cairo_window(t)[0], "2026-10-24T09:30Z")
            self.assertEqual(worker.scheduled_phase(worker.HALF_HOUR_CRON, t),
                             "interval")

    def test_2207_recovers_today_word_when_standard_daily_tick_is_missing(self):
        now = datetime(2026, 10, 24, 19, 7, tzinfo=timezone.utc)
        self.assertEqual(worker.scheduled_phase(worker.HALF_HOUR_CRON, now),
                         "skip")
        ledger = MagicMock()
        ledger.read.return_value = ({"entries": {}}, "sha")
        ledger.reserve.return_value = "reserved"
        with (
            patch.dict(os.environ, {"RASD_JOB_CRON":worker.HALF_HOUR_CRON}),
            patch.object(worker, "require_github_scheduler"),
            patch.object(worker, "protected_credentials",
                         return_value=("sender@example.com", "recipient@example.com",
                                       "offline-fake-secret", ledger)),
            patch.object(worker, "news_for_rollup", return_value=[]),
            patch.object(worker, "send_one_word",
                         return_value="<offline-2207-fixture@gmail.com>") as smtp,
        ):
            result = worker.run_scheduled("rollup_recovery", now)
        self.assertEqual(result["items"], 0)
        self.assertTrue(result["is_explicit_zero_accepted_news_notice"])
        self.assertEqual(ledger.reserve.call_args.args[0],
                         worker.digest_key("rollup:2026-10-24"))
        smtp.assert_called_once()

    def test_2200_cannot_recover_before_due_window(self):
        now=datetime(2026,10,24,19,0,tzinfo=timezone.utc)
        with (
            patch.dict(os.environ, {"RASD_JOB_CRON":worker.HALF_HOUR_CRON}),
            patch.object(worker, "require_github_scheduler"),
            patch.object(worker, "protected_credentials") as cred,
        ):
            result=worker.run_scheduled("rollup_recovery",now)
        self.assertEqual(result["status"],"skip_non_target_cairo_slot")
        cred.assert_not_called()

    def test_2207_no_interval_sends_competing_with_daily(self):
        now=datetime(2026,10,24,19,7,tzinfo=timezone.utc)
        with (
            patch.dict(os.environ, {"RASD_JOB_CRON":worker.HALF_HOUR_CRON}),
            patch.object(worker,"require_github_scheduler"),
            patch.object(worker,"protected_credentials") as cred,
        ):
            result=worker.run_scheduled("interval",now)
        self.assertEqual(result["status"],"skip_non_target_cairo_slot")
        cred.assert_not_called()


if __name__=="__main__":
    unittest.main()
