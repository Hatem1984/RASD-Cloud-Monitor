"""Reuse the actual scheduled worker in an isolated no-network workday mock.

The successful original-page Word builder is stubbed here; proof integrity is
enforced in its separate existing tests. This tests the send/CAS behavior.
"""
import copy
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import scheduled_rasd as rasd


def story(ident, headline, at):
    return {
        "id": ident * 24,
        "headline": headline,
        "publisher_excerpt": "تجربة مصطنعة فقط",
        "source": "fixture publisher",
        "url": "https://example.org/fixture/" + ident,
        "published_at_cairo": at,
        "published_display_cairo": at,
    }


class RealWorkerSmartRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.s1 = story("a", "خطة تمويل تجريبية مشروطة لمشروعات الطاقة",
                        "2026-10-27 10:00 EEST")
        self.s2 = story("b", "مشروع اقتصادي افتراضي للتصنيع والبحث والتطوير",
                        "2026-10-27 11:00 EEST")
        self.ledger = MagicMock()
        self.state = {"entries": {}}
        self.ledger.read.side_effect = lambda: (copy.deepcopy(self.state), "fixture-cas")
        self.config = {"feeds": [{"id": "source"}]}
        self.sent = []
        self.cas_reservations = []
        self.queue = []
        self.fail_once = False

    def _discover(self, config, clock, *, source_records, **kwargs):
        source_records.append({
            "feed_id": "source", "status": "ok", "verified_links": len(self.queue)})
        return copy.deepcopy(self.queue)

    def _prepare(self, items, config, output, **kwargs):
        return Path(output) / "synthetic-only.docx", copy.deepcopy(items), 0, False

    def _reserve(self, ledger, delivered, day):
        ids = [item["id"] for item in delivered]
        if any(i in self.state["entries"] for i in ids):
            raise RuntimeError("already_reserved")
        self.cas_reservations.extend(ids)
        for s in delivered:
            self.state["entries"][s["id"]] = {
                "kind": "interval_item", "status": "reserved", "news": s}
        return None

    def _smtp(self, *args, **kwargs):
        self.sent.append(kwargs["key"])
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("smtp_uncertain_reconcile_sent_manually")
        return "<test-receipt@example.invalid>"

    def _accepted(self, ids, message):
        for ident in ids:
            self.state["entries"][ident]["status"] = "smtp_accepted"
            self.state["entries"][ident]["message_id"] = message

    def tick(self, hour, minute, queue, *, image_held=False):
        self.queue = queue
        now = datetime(2026, 10, 27, hour, minute, tzinfo=rasd.CAIRO)
        prepare = (MagicMock(side_effect=RuntimeError(
            "no_original_publisher_page_verified")) if image_held else self._prepare)
        with (patch.object(rasd, "require_github_scheduler"),
              patch.object(rasd, "protected_credentials",
                           return_value=("from@example.invalid",
                                         "owner@example.invalid",
                                         "mock", self.ledger)),
              patch.object(rasd, "scheduled_phase", return_value="interval"),
              patch.object(rasd, "discover_interval_news", side_effect=self._discover),
              patch.object(rasd, "prepare_source_limited_verified_word",
                           side_effect=prepare),
              patch.object(rasd, "reserve_stories", side_effect=self._reserve),
              patch.object(rasd, "send_one_word", side_effect=self._smtp),
              patch.object(self.ledger, "mark_smtp_accepted_many", side_effect=self._accepted),
              patch.object(rasd.json, "loads", return_value=self.config),
              patch.dict(rasd.os.environ, {
                  "RASD_SMART_NO_EMPTY_INTERVAL_EMAIL": "true",
                  "GITHUB_EVENT_NAME": "schedule",
                  "RASD_JOB_CRON": rasd.HALF_HOUR_CRON,
              })):
            return rasd.run_scheduled("interval", now)

    def test_09_to_11_one_message_per_new_evidenced_article(self):
        self.assertEqual(self.tick(9, 0, [])["status"], "NO_NEW_VERIFIED_NEWS")
        self.assertEqual(self.tick(9, 30, [])["status"], "NO_NEW_VERIFIED_NEWS")
        first = self.tick(10, 0, [self.s1])
        self.assertEqual(first["status"], "smtp_accepted_unconfirmed_inbox")
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.tick(10, 30, [self.s1])["status"],
                         "NO_NEW_VERIFIED_NEWS")
        second = self.tick(11, 0, [self.s1, self.s2])
        self.assertEqual(second["status"], "smtp_accepted_unconfirmed_inbox")
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.cas_reservations, [self.s1["id"], self.s2["id"]])
        self.assertEqual(len(self.state["entries"]), 2)
        self.assertTrue(all(row["status"] == "smtp_accepted"
                            for row in self.state["entries"].values()))

    def test_original_publisher_screenshot_hold_no_send_no_cas(self):
        result = self.tick(10, 0, [self.s1], image_held=True)
        self.assertEqual(result["status"], "EVIDENCE_HOLD")
        self.assertFalse(result["smtp_accepted"])
        self.assertEqual(self.sent, [])
        self.assertEqual(self.cas_reservations, [])
        self.assertEqual(self.state["entries"], {})
        # Later proof success is permitted, without marking held article sent.
        self.assertEqual(self.tick(11, 0, [self.s1])["items"], 1)

    def test_uncertain_smtp_holds_reservation_and_never_blind_resends(self):
        self.fail_once = True
        with self.assertRaisesRegex(RuntimeError, "smtp_uncertain_reconcile_sent_manually"):
            self.tick(10, 0, [self.s1])
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.state["entries"][self.s1["id"]]["status"], "reserved")
        self.assertEqual(self.tick(10, 30, [self.s1])["status"],
                         "NO_NEW_VERIFIED_NEWS")
        self.assertEqual(len(self.sent), 1)

    def test_empty_and_held_ticks_do_not_touch_private_cas_write(self):
        for i in range(3):
            self.tick(9, 0, [])
        self.tick(10, 0, [self.s1], image_held=True)
        self.ledger.write.assert_not_called()
        self.ledger.reserve.assert_not_called()
        self.assertEqual(self.cas_reservations, [])


if __name__ == "__main__":
    unittest.main()
