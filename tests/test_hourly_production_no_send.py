"""Synthetic-only hourly cadence, atomic CAS reservation and report parity."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from rasd_hourly_delivery import hourly_period, hourly_slot_key, reserve_hourly_originals
import scheduled_rasd as worker


def item(i):
    url = f"https://hapijournal.com/planning-verified-{i}"
    from monitor import article_id
    return {
        "id": article_id(url), "headline": f"وزارة التخطيط — خبر {i}",
        "publisher_excerpt": "", "source": "Hapi native news RSS",
        "url": url, "published_at_cairo": f"2026-11-19 19:{i:02d} EET",
        "published_display_cairo": "19 نوفمبر 2026",
    }


def ledger_state():
    return {"schema_version": 2, "entries": {},
            "approved_recipient_sha256": "a" * 64}


class HourlyProductionNoSend(unittest.TestCase):
    def setUp(self):
        self.clock = datetime(2026, 11, 19, 18, 7, tzinfo=timezone.utc)
        self.env = patch.dict(os.environ, {
            "GITHUB_EVENT_NAME": "schedule",
            "RASD_JOB_CRON": worker.HALF_HOUR_CRON,
            "RASD_HOURLY_REPORTS_ENABLED": "true",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_hourly_window_is_full_previous_clock_hour(self):
        a, b, key = hourly_period(self.clock)
        self.assertEqual(a.isoformat(), "2026-11-19T17:00:00+00:00")
        self.assertEqual(b.isoformat(), "2026-11-19T18:00:00+00:00")
        self.assertEqual(key, "2026-11-19T18:00Z")
        self.assertEqual(hourly_period(self.clock + timedelta(minutes=11))[2], key)
        self.assertNotEqual(hourly_slot_key(key),
                            hourly_slot_key("2026-11-19T19:00Z"))
        with self.assertRaises(ValueError):
            hourly_slot_key("https://example.org/foo")

    def test_seven_news_and_one_hour_share_single_atomic_private_CAS(self):
        ledger = MagicMock()
        ledger.read.return_value = (ledger_state(), "private-old-sha")
        seven = [item(i) for i in range(7)]
        first = reserve_hourly_originals(
            ledger, seven, "2026-11-19", "2026-11-19T18:00Z")
        ledger.write.assert_called_once()
        proposed, sha = ledger.write.call_args.args
        self.assertEqual(sha, "private-old-sha")
        self.assertEqual(proposed["entries"][first]["kind"], "hourly_slot")
        self.assertEqual(proposed["entries"][first]["item_ids"],
                         [x["id"] for x in seven])
        self.assertEqual(len(proposed["entries"]), 8)
        self.assertTrue(all(proposed["entries"][x["id"]]["status"] == "reserved"
                            for x in seven))
        ledger.read.return_value = (copy.deepcopy(proposed), "new-sha")
        with self.assertRaisesRegex(RuntimeError,
                                    "hourly_delivery_slot_reserved_manual_review"):
            reserve_hourly_originals(
                ledger, seven, "2026-11-19", "2026-11-19T18:00Z")
        ledger.write.assert_called_once()

    def test_second_half_hour_slot_skips_without_any_private_io(self):
        with patch.object(worker, "require_github_scheduler"), \
             patch.object(worker, "protected_credentials") as secrets, \
             patch.object(worker, "discover_interval_news") as discover:
            outcome = worker.run_scheduled(
                "interval", self.clock + timedelta(minutes=30))
        self.assertEqual(outcome["status"], "skip_non_target_cairo_slot")
        secrets.assert_not_called()
        discover.assert_not_called()

    def test_hourly_seven_items_use_same_report_layout_with_one_mail_attempt(self):
        seven = [item(i) for i in range(7)]
        ledger = MagicMock()
        ledger.read.return_value = (ledger_state(), "sha")
        source_rows = [{"feed_id": "hapi", "status": "ok"}]
        fixture_doc = Path(tempfile.gettempdir()) / "hourly-offline-placeholder.docx"
        def discover(config, now, *, allow_degraded, source_records, published_before):
            self.assertEqual(published_before.isoformat(), "2026-11-19T18:00:00+00:00")
            self.assertTrue(allow_degraded)
            source_records.extend(source_rows)
            return seven
        def prepare(rows, config, out, **kwargs):
            self.assertEqual(kwargs["report_kind"], "hourly")
            self.assertIn("تقرير المتابعة الساعية", kwargs["title"])
            self.assertEqual(kwargs["end"], worker.cairo_display_time(
                datetime(2026, 11, 19, 18, tzinfo=timezone.utc)))
            self.assertEqual(rows, seven)
            return fixture_doc, seven, 0, False
        with patch.object(worker, "require_github_scheduler"), \
             patch.object(worker, "protected_credentials",
                          return_value=("sender@gmail.com", "owner@example.org", "pw", ledger)), \
             patch.object(worker, "discover_interval_news", side_effect=discover), \
             patch.object(worker, "prepare_source_limited_verified_word", side_effect=prepare), \
             patch.object(worker, "reserve_hourly_originals",
                          return_value=hourly_slot_key("2026-11-19T18:00Z")) as reserve, \
             patch.object(worker, "send_one_word",
                          return_value="<rasd-offline-test@gmail.com>") as sent:
            outcome = worker.run_scheduled("interval", self.clock)
        self.assertEqual(outcome["items"], 7)
        self.assertEqual(outcome["hourly_target_minimum"], 6)
        self.assertEqual(outcome["hourly_target_shortfall"], 0)
        reserve.assert_called_once()
        sent.assert_called_once()
        ledger.mark_smtp_accepted_many.assert_called_once()
        ledger.mark_smtp_accepted.assert_called_once()
        self.assertEqual(ledger.mark_smtp_accepted_many.call_args.args[0],
                         [x["id"] for x in seven])

    def test_same_hour_reserved_slot_prevents_any_second_email(self):
        state = ledger_state()
        key = hourly_slot_key("2026-11-19T18:00Z")
        state["entries"][key] = {
            "kind": "hourly_slot", "status": "reserved", "reserved_at": "test"}
        ledger = MagicMock()
        ledger.read.return_value = (state, "sha")
        with patch.object(worker, "require_github_scheduler"), \
             patch.object(worker, "protected_credentials",
                          return_value=("sender@gmail.com", "owner@example.org", "pw", ledger)), \
             patch.object(worker, "discover_interval_news") as discover, \
             patch.object(worker, "send_one_word") as sent:
            result = worker.run_scheduled(
                "interval", self.clock + timedelta(minutes=11))
        self.assertEqual(result["status"], "hourly_slot_already_reserved_or_sent")
        discover.assert_not_called()
        sent.assert_not_called()


if __name__ == "__main__":
    unittest.main()
