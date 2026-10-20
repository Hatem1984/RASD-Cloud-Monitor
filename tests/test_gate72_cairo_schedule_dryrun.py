"""Gate72: date/DST timing safety; every test remains NO CRON and NO SMTP."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from gate72_cairo_schedule_dryrun import (
    dry_run_daily_plan, next_safe_cairo_tick,
)

CAIRO=ZoneInfo("Africa/Cairo")


def at(day,hour,minute=0):
    return datetime(day.year,day.month,day.day,hour,minute,tzinfo=CAIRO)


class CairoSchedulerNoCronTests(unittest.TestCase):
    def test_before_eight_never_dispatches_partial_day(self):
        p=dry_run_daily_plan(datetime(2026,10,20,7,59,tzinfo=CAIRO))
        self.assertEqual(p["status"],"WAIT_CAIRO_LOCAL_08_00_NOT_DUE")
        self.assertEqual(p["target_completed_cairo_day"],"2026-10-19")
        self.assertFalse(p["job_dispatched"])
        self.assertFalse(p["email_sent"])

    def test_eight_am_window_is_still_only_dry_run(self):
        p=dry_run_daily_plan(datetime(2026,10,20,8,0,tzinfo=CAIRO))
        self.assertEqual(p["status"],"DRYRUN_READY_WINDOW_ONLY")
        self.assertFalse(p["production_scheduler_enabled"])
        self.assertFalse(p["production_approved"])

    def test_after_window_never_auto_catches_up(self):
        p=dry_run_daily_plan(datetime(2026,10,20,9,0,tzinfo=CAIRO))
        self.assertEqual(p["status"],
                         "MISSED_WINDOW_REQUIRE_OPERATOR_REVIEW_NO_AUTO_CATCHUP")
        self.assertFalse(p["job_dispatched"])

    def test_principal_report_identity_stable_same_day(self):
        early=dry_run_daily_plan(datetime(2026,10,20,7,0,tzinfo=CAIRO))
        due=dry_run_daily_plan(datetime(2026,10,20,8,20,tzinfo=CAIRO))
        late=dry_run_daily_plan(datetime(2026,10,20,23,0,tzinfo=CAIRO))
        self.assertEqual(early["report_identity"],due["report_identity"])
        self.assertEqual(due["report_identity"],late["report_identity"])
        self.assertEqual(due["target_completed_cairo_day"],"2026-10-19")

    def test_next_day_changes_id_without_auto_resend(self):
        a=dry_run_daily_plan(datetime(2026,10,20,8,10,tzinfo=CAIRO))
        b=dry_run_daily_plan(datetime(2026,10,21,8,10,tzinfo=CAIRO))
        self.assertNotEqual(a["report_identity"],b["report_identity"])
        self.assertTrue(a["requires_explicit_transport_approval"])
        self.assertTrue(b["requires_explicit_transport_approval"])

    def test_dryrun_uses_cairo_zone_even_if_utc_clock_supplied(self):
        p=dry_run_daily_plan(datetime(2026,10,20,5,0,tzinfo=timezone.utc))
        self.assertEqual(p["current_cairo_day"],"2026-10-20")
        self.assertEqual(p["status"],"DRYRUN_READY_WINDOW_ONLY")

    def test_next_tick_strictly_in_future_after_eight(self):
        t=next_safe_cairo_tick(datetime(2026,10,20,8,0,tzinfo=CAIRO))
        self.assertEqual(t.date().isoformat(),"2026-10-21")
        self.assertEqual(t.hour,8)
        self.assertEqual(t.minute,0)

    def test_cairo_dst_is_not_hardcoded_utc_plus_three(self):
        winter=next_safe_cairo_tick(
            datetime(2026,1,15,5,0,tzinfo=timezone.utc))
        summer=next_safe_cairo_tick(
            datetime(2026,7,15,4,0,tzinfo=timezone.utc))
        self.assertEqual(winter.astimezone(timezone.utc).hour,6)
        self.assertEqual(summer.astimezone(timezone.utc).hour,5)
        self.assertEqual(winter.hour,8)
        self.assertEqual(summer.hour,8)

    def test_naive_or_non_datetime_clock_refused(self):
        for x in (datetime(2026,10,20,8,0),None,"2026-10-20"):
            with self.subTest(x=str(x)),self.assertRaisesRegex(ValueError,
                                                               "requires_aware_clock"):
                dry_run_daily_plan(x)
            with self.assertRaisesRegex(ValueError,"requires_aware_clock"):
                next_safe_cairo_tick(x)

    def test_no_credentials_network_smtp_or_actual_schedule(self):
        c=(Path(__file__).resolve().parents[1] /
           "gate72_cairo_schedule_dryrun.py").read_text()
        for banned in ("smtplib","boto3","PrivateGitHubLedger",
                       "send_message(","APScheduler","cron:",
                       "GITHUB_TOKEN","RASD_GMAIL_APP_PASSWORD"):
            self.assertNotIn(banned,c)


if __name__=="__main__":
    unittest.main()
