"""Recover a missed Cairo 22:00 rollup from the next true schedule slot.

All mail and ledger operations are replaced by offline mocks.
"""
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import scheduled_rasd as worker


class DailyCatchUp(unittest.TestCase):
    def setUp(self):
        # Only this offline fixture emulates a genuinely scheduled worker.
        # Production event authentication remains strictly fail-closed.
        self._scheduled_env = patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule"})
        self._scheduled_env.start()
        self.addCleanup(self._scheduled_env.stop)

    def check_recovery(self, clock, expected_day):
        ledger = MagicMock()
        ledger.read.return_value = ({"entries": {}}, "sha")
        ledger.reserve.return_value = "reserved"
        seen_days = []
        def inspect_previous(state, day, config):
            seen_days.append(day)
            return []
        with (
            patch.dict(os.environ, {"RASD_JOB_CRON": worker.HALF_HOUR_CRON}),
            patch.object(worker, "require_github_scheduler"),
            patch.object(worker, "protected_credentials",
                         return_value=("sender", "recipient", "not-used", ledger)),
            patch.object(worker, "news_for_rollup", side_effect=inspect_previous),
            patch.object(worker, "send_one_word",
                         return_value="<rasd-recovery-fixture@gmail.com>") as send,
        ):
            result = worker.run_scheduled("rollup_recovery", clock)
        self.assertEqual(seen_days, [expected_day])
        self.assertEqual(result["items"], 0)
        self.assertTrue(result["is_explicit_zero_accepted_news_notice"])
        self.assertEqual(ledger.reserve.call_count, 1)
        self.assertEqual(
            ledger.reserve.call_args.args[0],
            worker.digest_key("rollup:" + expected_day))
        self.assertEqual(send.call_count, 1)
        ledger.mark_smtp_accepted.assert_called_once()
        return result

    def test_missed_yesterday_at_late_afternoon_cairo_needs_manual_review(self):
        # More than four hours after due: release must not silently email
        # yesterday's missed report or even read private CAS.
        clock = datetime(2026, 10, 23, 13, 30, tzinfo=timezone.utc)
        with (
            patch.dict(os.environ, {"RASD_JOB_CRON": worker.HALF_HOUR_CRON}),
            patch.object(worker, "require_github_scheduler"),
            patch.object(worker, "protected_credentials") as credentials,
            patch.object(worker, "send_one_word") as send,
        ):
            result = worker.run_scheduled("rollup_recovery", clock)
        self.assertEqual(result["status"],
                         "expired_daily_recovery_requires_owner_review")
        credentials.assert_not_called()
        send.assert_not_called()

    def test_current_day_after_cairo_22_30(self):
        self.check_recovery(datetime(2026, 10, 23, 19, 30,
                                     tzinfo=timezone.utc), "2026-10-23")

    def test_winter_offset_uses_actual_cairo_date(self):
        # Winter: Nov 2 at 22:00 Cairo is 20:00 UTC; four hours later
        # remains a valid last-chance recovery in the 02:00 Cairo slot.
        self.check_recovery(datetime(2026, 11, 3, 0, 0,
                                     tzinfo=timezone.utc), "2026-11-02")

    def test_pre_existing_daily_reservation_skips_before_smtp(self):
        ledger=MagicMock()
        key=worker.digest_key("rollup:2026-10-22")
        ledger.read.return_value=(
            {"entries":{key:{"status":"reserved"}}},"sha")
        with (
            patch.dict(os.environ,{"RASD_JOB_CRON":worker.HALF_HOUR_CRON}),
            patch.object(worker,"require_github_scheduler"),
            patch.object(worker,"protected_credentials",
                return_value=("sender","recipient","not-used",ledger)),
            patch.object(worker,"send_one_word") as send,
        ):
            result=worker.run_scheduled(
                "rollup_recovery",
                datetime(2026,10,22,21,30,tzinfo=timezone.utc))
        self.assertEqual(result["status"],"rollup_reserved_pending_manual_reconciliation")
        send.assert_not_called()
        ledger.reserve.assert_not_called()

    def test_recovery_forbids_manual_or_daily_cron_context(self):
        with (
            patch.dict(os.environ,{"RASD_JOB_CRON":worker.DAILY_CRON}),
            patch.object(worker,"require_github_scheduler"),
            patch.object(worker,"protected_credentials") as credentials,
        ):
            with self.assertRaisesRegex(
                RuntimeError,"daily_recovery_not_half_hour_schedule"):
                worker.run_scheduled(
                    "rollup_recovery",
                    datetime(2026,10,23,19,30,tzinfo=timezone.utc))
        credentials.assert_not_called()

    def test_skip_at_22_00_collision_with_real_daily(self):
        with (
            patch.dict(os.environ,{"RASD_JOB_CRON":worker.HALF_HOUR_CRON}),
            patch.object(worker,"require_github_scheduler"),
            patch.object(worker,"protected_credentials") as credentials,
        ):
            result=worker.run_scheduled(
                "rollup_recovery",
                datetime(2026,10,23,19,0,tzinfo=timezone.utc))
        self.assertEqual(result["status"],"skip_non_target_cairo_slot")
        credentials.assert_not_called()


if __name__=="__main__":
    unittest.main()
