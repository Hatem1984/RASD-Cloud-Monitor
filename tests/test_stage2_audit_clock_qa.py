"""Offline regression for delayed Cairo 22:10 GitHub Actions QA day audit."""
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from rasd_stage2_audit_clock_qa import target_day_for_daily_audit

CAIRO = ZoneInfo("Africa/Cairo")


class DailyAuditClockQA(unittest.TestCase):
    def test_on_time_2210_selects_current_day(self):
        d = target_day_for_daily_audit(datetime(2026, 11, 5, 22, 10, tzinfo=CAIRO))
        self.assertEqual(d.isoformat(), "2026-11-05")

    def test_delayed_after_midnight_preserves_yesterday(self):
        d = target_day_for_daily_audit(datetime(2026, 11, 5, 2, 53, tzinfo=CAIRO))
        self.assertEqual(d.isoformat(), "2026-11-04")

    def test_late_but_still_within_8_hours(self):
        d = target_day_for_daily_audit(datetime(2026, 11, 6, 5, 59, tzinfo=CAIRO))
        self.assertEqual(d.isoformat(), "2026-11-05")

    def test_after_8_hours_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "too_late_hold"):
            target_day_for_daily_audit(datetime(2026, 11, 5, 12, 38, tzinfo=CAIRO))

    def test_just_before_ten_ten_is_not_a_same_day_audit(self):
        with self.assertRaisesRegex(ValueError, "too_late_hold"):
            target_day_for_daily_audit(datetime(2026, 11, 5, 22, 9, tzinfo=CAIRO))

    def test_naive_clock_refused(self):
        with self.assertRaisesRegex(ValueError, "must_be_aware"):
            target_day_for_daily_audit(datetime(2026, 11, 5, 22, 10))

    def test_utc_day_boundary_always_resolves_cairo(self):
        # November is Cairo UTC+2. 00:53 UTC is 02:53 Cairo.
        d = target_day_for_daily_audit(datetime(2026, 11, 5, 0, 53, tzinfo=timezone.utc))
        self.assertEqual(d.isoformat(), "2026-11-04")

    def test_dst_summer_after_midnight(self):
        d = target_day_for_daily_audit(datetime(2026, 7, 15, 0, 40, tzinfo=CAIRO))
        self.assertEqual(d.isoformat(), "2026-07-14")


if __name__ == "__main__":
    unittest.main()
