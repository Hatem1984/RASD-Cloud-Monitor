"""Owner-approved hourly zero-news Word: strict CAS/no-send regression.

Tests never send SMTP or mutate GitHub private state. They deliberately
leave the existing half-hour production behavior unchanged until release.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from docx import Document

import scheduled_rasd as worker
from rasd_hourly_delivery import hourly_period, hourly_slot_key


class HourlyEmptyStatusNoSend(unittest.TestCase):
    now = datetime(2026, 11, 21, 14, 7, tzinfo=timezone.utc)

    def setUp(self):
        self.ledger = MagicMock()
        self.ledger.reserve.return_value = "reserved"
        self.news = {"feeds": [
            {"id":"hapi"}, {"id":"shorouk"}]}
        self.health = [
            {"feed_id":"hapi","status":"ok","verified_links":4},
            {"feed_id":"shorouk","status":"ok","verified_links":6}]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def call(self,*,state=None,health=None,held_articles=0):
        start,end,slot=hourly_period(self.now)
        return worker.send_empty_interval_status(
            ledger=self.ledger, sender="source@gmail.com",
            recipient="testonly@example.com", password="mock",
            state=state if state is not None else {"entries":{}},
            config=self.news,
            health=health if health is not None else self.health,
            window=slot,start=start,now=self.now,
            output=Path(self.tmp.name),
            held_articles=held_articles,hourly=True)

    def test_genuine_empty_hour_sends_one_truthful_zero_news_word(self):
        with patch.object(worker,"send_one_word",
                          return_value="<rasd-hour-status@example.com>") as send:
            result=self.call()
        self.assertEqual(result["items"],0)
        self.assertTrue(result["smtp_accepted"])
        start,end,slot=hourly_period(self.now)
        key=hourly_slot_key(slot)
        self.assertEqual(send.call_args.kwargs["key"],key)
        self.assertIn("المتابعة الساعية",send.call_args.kwargs["subject"])
        self.assertIn("الساعة المكتملة",send.call_args.kwargs["body_text"])
        word=Document(send.call_args.args[0])
        self.assertEqual(len(word.inline_shapes),0)
        text="\n".join(p.text for p in word.paragraphs)
        self.assertIn("لا يثبت ذلك عدم نشر أخبار",text)
        self.assertIn("حالة المصادر",text)
        self.ledger.reserve.assert_called_once_with(key,"testonly@example.com")
        self.ledger.mark_smtp_accepted.assert_called_once_with(
            key,"<rasd-hour-status@example.com>")

    def test_hourly_status_and_verified_news_use_exact_same_slot(self):
        _,_,slot=hourly_period(self.now)
        shared=hourly_slot_key(slot)
        with patch.object(worker,"send_one_word") as send:
            result=self.call(state={"entries": {
                shared:{"kind":"hourly_slot","status":"reserved"}}})
        self.assertEqual(result["status"],"interval_status_already_reserved_or_sent")
        self.ledger.reserve.assert_not_called()
        send.assert_not_called()

    def test_source_failure_is_not_announced_as_no_news_in_all_sources(self):
        failed=[
            self.health[0],
            {"feed_id":"shorouk","status":"failed","verified_links":0,
             "failure_code":"other"}]
        with patch.object(worker,"send_one_word",
                          return_value="<rasd-hour-status@example.com>") as send:
            result=self.call(health=failed)
        self.assertTrue(result["source_limited"])
        text="\n".join(p.text for p in Document(send.call_args.args[0]).paragraphs)
        self.assertIn("التغطية جزئية",text)
        self.assertIn("تعذّر",text)

    def test_unverified_original_photo_is_honest_hold_not_zero_published(self):
        with patch.object(worker,"send_one_word",
                          return_value="<rasd-hour-status@example.com>") as send:
            result=self.call(held_articles=1)
        self.assertEqual(result["held_articles"],1)
        self.assertTrue(result["source_limited"])
        text="\n".join(p.text for p in Document(send.call_args.args[0]).paragraphs)
        self.assertIn("معلّقة",text)
        self.assertNotIn("لم يُعثر على أخبار جديدة مطابقة",text)

    def test_wrong_hour_start_fails_before_reserving_email(self):
        _,_,slot=hourly_period(self.now)
        with patch.object(worker,"send_one_word") as send:
            with self.assertRaisesRegex(RuntimeError,"hourly_status_window_identity_hold"):
                worker.send_empty_interval_status(
                    ledger=self.ledger, sender="source@gmail.com",
                    recipient="testonly@example.com",password="mock",
                    state={"entries":{}},config=self.news,health=self.health,
                    window=slot,start=self.now,now=self.now,
                    output=Path(self.tmp.name),hourly=True)
        self.ledger.reserve.assert_not_called()
        send.assert_not_called()

    def test_hourly_owner_policy_overrides_old_skip_empty_but_only_hourly(self):
        now=datetime(2026,11,20,18,7,tzinfo=timezone.utc)
        with patch.object(worker,"require_github_scheduler"),\
             patch.object(worker,"protected_credentials",
                          return_value=("source@gmail.com","testonly@example.com",
                                        "offline",self.ledger)),\
             patch.object(worker,"discover_interval_news",return_value=[]),\
             patch.object(worker,"send_empty_interval_status",
                          return_value={"status":"mock_hourly_status"}) as notify,\
             patch.object(worker,"smart_interval_no_mail") as skip,\
             patch.dict(worker.os.environ,{
                 "GITHUB_EVENT_NAME":"schedule",
                 "RASD_JOB_CRON":worker.HALF_HOUR_CRON,
                 "RASD_HOURLY_REPORTS_ENABLED":"true",
                 "RASD_SMART_NO_EMPTY_INTERVAL_EMAIL":"true",
             }):
            self.ledger.read.return_value=({"entries":{}},"sha")
            result=worker.run_scheduled("interval",now)
        self.assertEqual(result["status"],"mock_hourly_status")
        self.assertTrue(notify.call_args.kwargs["hourly"])
        skip.assert_not_called()


if __name__=="__main__":
    unittest.main()
