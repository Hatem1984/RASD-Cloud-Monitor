"""Synthetic-only hourly cadence, atomic CAS reservation and report parity."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from rasd_hourly_delivery import (
    hourly_period, hourly_slot_key, hourly_delivery_eligible, reserve_hourly_originals)
import scheduled_rasd as worker


def item(i):
    url = f"https://hapijournal.com/planning-verified-{i}"
    from monitor import article_id
    return {
        "id": article_id(url), "headline": f"وزارة التخطيط — خبر {i}",
        "publisher_excerpt": "", "source": "Hapi native news RSS",
        "url": url, "published_utc": f"2026-11-19T17:{i:02d}:00+00:00",
        "published_at_cairo": f"2026-11-19 19:{i:02d} EET",
        "published_display_cairo": "19 نوفمبر 2026",
        "hourly_publication_bucket": "within_previous_hour",
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

    def test_2200_cairo_daily_rollup_has_unique_later_hourly_opportunity(self):
        from daily_report import CAIRO
        # Winter UTC+2: Cairo 22:05 is reserved for daily, 22:37 for
        # the immediately preceding full hour, followed by 23:07 next slot.
        winter_daily = datetime(2026, 11, 20, 20, 5, tzinfo=timezone.utc)
        winter_hourly = datetime(2026, 11, 20, 20, 37, tzinfo=timezone.utc)
        winter_next = datetime(2026, 11, 20, 21, 7, tzinfo=timezone.utc)
        self.assertFalse(hourly_delivery_eligible(winter_daily, CAIRO))
        self.assertTrue(hourly_delivery_eligible(winter_hourly, CAIRO))
        self.assertTrue(hourly_delivery_eligible(winter_next, CAIRO))
        self.assertEqual(hourly_period(winter_hourly)[2],
                         "2026-11-20T20:00Z")
        self.assertEqual(hourly_period(winter_next)[2],
                         "2026-11-20T21:00Z")
        self.assertNotEqual(hourly_slot_key(hourly_period(winter_hourly)[2]),
                            hourly_slot_key(hourly_period(winter_next)[2]))
        # Summer UTC+3 Cairo: the same behavior with different UTC wall time.
        summer_daily = datetime(2026, 7, 20, 19, 5, tzinfo=timezone.utc)
        summer_hourly = datetime(2026, 7, 20, 19, 37, tzinfo=timezone.utc)
        self.assertFalse(hourly_delivery_eligible(summer_daily, CAIRO))
        self.assertTrue(hourly_delivery_eligible(summer_hourly, CAIRO))
        self.assertEqual(hourly_period(summer_hourly)[2],
                         "2026-07-20T19:00Z")
        # All other half-hour reruns are forbidden for SMTP.
        self.assertFalse(hourly_delivery_eligible(winter_next + timedelta(minutes=30), CAIRO))

    def test_protected_2237_cairo_hourly_enters_normal_no_send_path(self):
        from daily_report import CAIRO
        at_2237 = datetime(2026, 11, 20, 20, 37, tzinfo=timezone.utc)
        self.assertEqual(worker.scheduled_phase(worker.HALF_HOUR_CRON, at_2237),
                         "interval")
        with patch.object(worker, "require_github_scheduler"), \
             patch.object(worker, "protected_credentials") as credential_probe:
            with self.assertRaises(ValueError):
                # No fake credentials in this test; proving that it reaches
                # authentication gate, rather than the previous silent skip.
                worker.run_scheduled("interval", at_2237)
        credential_probe.assert_called_once()

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

    def test_seven_from_one_publisher_become_one_genuine_partial_word(self):
        seven=[item(i) for i in range(7)]
        ledger=MagicMock()
        ledger.read.return_value=(ledger_state(),"sha")
        def discover(config,now,*,allow_degraded,source_records,published_before):
            self.assertEqual(published_before.isoformat(),
                             "2026-11-19T18:00:00+00:00")
            source_records.extend({
                "feed_id":f["id"],"status":"ok","verified_links":0
            } for f in config["feeds"])
            return seven
        def prepare(rows,config,out,**kwargs):
            self.assertEqual(len(rows),1)
            self.assertEqual(kwargs["report_kind"],"hourly")
            return (Path(tempfile.gettempdir())/"offline-one.docx",
                    [{**rows[0],"evidence_image_path":"synthetic-only.jpg"}],
                    0,True)
        with patch.object(worker,"require_github_scheduler"), \
             patch.object(worker,"protected_credentials",
                          return_value=("sender@gmail.com","owner@example.org",
                                        "pw",ledger)), \
             patch.object(worker,"discover_interval_news",side_effect=discover), \
             patch.object(worker,"prepare_source_limited_verified_word",
                          side_effect=prepare) as prepared, \
             patch.object(worker,"send_empty_interval_status") as status, \
             patch.object(worker,"reserve_hourly_originals",
                          return_value=hourly_slot_key("2026-11-19T18:00Z")) as reserve, \
             patch.object(worker,"send_one_word",
                          return_value="<rasd-test-one@gmail.com>") as sent:
            result=worker.run_scheduled("interval",self.clock)
        self.assertEqual(result["items"],1)
        self.assertEqual(result["hourly_target_minimum"],10)
        self.assertEqual(result["hourly_target_shortfall"],9)
        self.assertEqual(result["status"],
                         "hourly_partial_smtp_accepted_unconfirmed_inbox")
        self.assertIn("1 أخبار موثقة من أصل 10",
                      sent.call_args.kwargs["subject"])
        prepared.assert_called_once()
        status.assert_not_called()
        reserve.assert_called_once()
        sent.assert_called_once()
        ledger.mark_smtp_accepted_many.assert_called_once()
        ledger.mark_smtp_accepted.assert_called_once()

    def test_ten_fresh_publisher_stories_use_same_word_layout_and_one_mail(self):
        import json
        from monitor import article_id
        config=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
        ten=[]
        for i,feed in enumerate(config["feeds"][:10]):
            url=f"https://{feed['allowed_article_hosts'][0]}/planning-verified-{i+11}"
            ten.append({
                "id":article_id(url),"headline":f"وزارة التخطيط تنفذ مشروع رقم {i+11}",
                "publisher_excerpt":"","source":feed["name"],"url":url,
                "published_utc":f"2026-11-19T17:{i:02d}:00+00:00",
                "published_at_cairo":f"2026-11-19 19:{i:02d} EET",
                "published_display_cairo":"19 نوفمبر 2026",
                "hourly_publication_bucket":"within_previous_hour",
            })
        ledger=MagicMock()
        ledger.read.return_value=(ledger_state(),"sha")
        verified_out=[]
        def discover(config,now,*,allow_degraded,source_records,published_before):
            source_records.extend({"feed_id":f["id"],"status":"ok",
                                   "verified_links":1} for f in config["feeds"])
            return ten
        def prepare(rows,config,out,**kwargs):
            self.assertEqual(kwargs["report_kind"],"hourly")
            self.assertIn("تقرير المتابعة الساعية",kwargs["title"])
            self.assertEqual(len(rows),10)
            self.assertEqual(len({i["source"] for i in rows}),10)
            verified_out.extend({**row,"evidence_image_path":"synthetic-only-not-a-real-photo.jpg"}
                                for row in rows)
            return Path(tempfile.gettempdir()) / "offline-placeholder.docx",verified_out,0,False
        with patch.object(worker,"require_github_scheduler"), \
             patch.object(worker,"protected_credentials",
                          return_value=("sender@gmail.com","owner@example.org","pw",ledger)), \
             patch.object(worker,"discover_interval_news",side_effect=discover), \
             patch.object(worker,"prepare_source_limited_verified_word",side_effect=prepare), \
             patch.object(worker,"reserve_hourly_originals",
                          return_value=hourly_slot_key("2026-11-19T18:00Z")) as reserve, \
             patch.object(worker,"send_one_word",
                          return_value="<rasd-offline-test@gmail.com>") as sent, \
             patch.object(worker,"send_empty_interval_status") as status:
            result=worker.run_scheduled("interval",self.clock)
        self.assertEqual(result["items"],10)
        self.assertEqual(result["hourly_target_minimum"],10)
        self.assertEqual(result["hourly_target_shortfall"],0)
        self.assertEqual(result["hourly_new_within_period"],10)
        self.assertEqual(result["hourly_recovered_older"],0)
        reserve.assert_called_once()
        sent.assert_called_once()
        status.assert_not_called()
        ledger.mark_smtp_accepted_many.assert_called_once()
        ledger.mark_smtp_accepted.assert_called_once()

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
