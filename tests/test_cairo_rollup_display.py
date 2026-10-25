"""Offline regression for Arabic Cairo rollup headings; NEVER SMTP or ledger."""
import unittest

from scheduled_rasd import cairo_rollup_label, digest_key


class CairoDailyLabels(unittest.TestCase):
    def test_october_evidence_title_has_no_iso_reordering(self):
        label, closing = cairo_rollup_label("2026-10-24")
        self.assertEqual(label, "٢٤ أكتوبر ٢٠٢٦")
        self.assertEqual(closing, "٢٤ أكتوبر ٢٠٢٦، الساعة ٢٢:٠٠ بتوقيت القاهرة")
        self.assertNotIn("2026-10-24", closing)

    def test_winter_and_summer_have_exact_cairo_wall_time(self):
        for day, month in [("2026-07-05", "يوليو"), ("2026-12-05", "ديسمبر")]:
            label, closing = cairo_rollup_label(day)
            self.assertIn(month, label)
            self.assertTrue(closing.endswith("الساعة ٢٢:٠٠ بتوقيت القاهرة"))

    def test_display_changes_do_not_change_delivery_id(self):
        day = "2026-10-24"
        immutable = digest_key("daily:" + day)
        self.assertNotEqual(cairo_rollup_label(day)[0], day)
        self.assertEqual(immutable, digest_key("daily:" + day))

    def test_invalid_day_fails_closed(self):
        with self.assertRaises(ValueError):
            cairo_rollup_label("2026-13-24")


if __name__ == "__main__":
    unittest.main()
