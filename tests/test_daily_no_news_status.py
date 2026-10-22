"""Daily truthful zero-accepted-news Word via protected CAS, offline only."""
from __future__ import annotations
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from docx import Document
import scheduled_rasd as rasd


class ZeroNewsDailyStatus(unittest.TestCase):
    def test_github_delayed_daily_schedule_does_not_shift_next_date(self):
        # Oct 22 Cairo EEST (+03) corresponds to 19:00 UTC. 22:54 Cairo
        # must still be accepted as the same summary, 23:00 must never.
        self.assertEqual(rasd.scheduled_phase(
            rasd.DAILY_CRON,datetime(2026,10,22,19,54,tzinfo=timezone.utc)),
            "rollup")
        self.assertEqual(rasd.scheduled_phase(
            rasd.DAILY_CRON,datetime(2026,10,22,20,0,tzinfo=timezone.utc)),
            "skip")

    def test_no_verified_news_delivers_honest_word_once_no_fake_photos(self):
        ledger=MagicMock()
        ledger.read.return_value=({"entries":{}},"sha-initial")
        ledger.reserve.return_value="reserved"
        mailed=[]
        def fake_smtp(word, **kw):
            document=Document(word)
            texts="\n".join(x.text for x in document.paragraphs)
            self.assertIn("لا أخبار مصوّرة",texts)
            self.assertIn("ليس تقرير تغطية صحفية كاملة",texts)
            self.assertIn("لا يثبت عدم نشر أخبار",texts)
            self.assertEqual(len(document.inline_shapes),0)
            self.assertGreater(word.stat().st_size,3000)
            self.assertIn("لا أخبار مصوّرة",kw["subject"])
            mailed.append((kw["key"],word.name))
            return "<rasd-fixture-daily@gmail.com>"
        with patch.object(rasd,"require_github_scheduler"), \
             patch.object(rasd,"scheduled_phase",return_value="rollup"), \
             patch.object(rasd,"protected_credentials",
                          return_value=("owner-sender@gmail.com","approved@example.org",
                                        "offline-password",ledger)), \
             patch.object(rasd,"news_for_rollup",return_value=[]), \
             patch.object(rasd,"send_one_word",side_effect=fake_smtp):
            result=rasd.run_scheduled(
                "rollup",datetime(2026,10,22,19,5,tzinfo=timezone.utc))
        self.assertEqual(result["items"],0)
        self.assertTrue(result["is_explicit_zero_accepted_news_notice"])
        self.assertIn("smtp_accepted_unconfirmed_inbox",result["status"])
        self.assertEqual(len(mailed),1)
        ledger.reserve.assert_called_once()
        ledger.mark_smtp_accepted.assert_called_once()
        self.assertEqual(ledger.mark_smtp_accepted.call_args.args[1],
                         "<rasd-fixture-daily@gmail.com>")

    def test_existing_daily_ledger_reservation_never_attempts_another_mail(self):
        ledger=MagicMock()
        day="2026-10-22"
        rollup_key=rasd.digest_key("rollup:"+day)
        ledger.read.return_value=({"entries":{rollup_key:{"status":"reserved"}}},"sha")
        with patch.object(rasd,"require_github_scheduler"), \
             patch.object(rasd,"scheduled_phase",return_value="rollup"), \
             patch.object(rasd,"protected_credentials",
                          return_value=("owner-sender@gmail.com","approved@example.org",
                                        "offline-password",ledger)), \
             patch.object(rasd,"news_for_rollup",
                          side_effect=AssertionError("reopened accepted news")), \
             patch.object(rasd,"send_one_word",
                          side_effect=AssertionError("duplicate SMTP")):
            result=rasd.run_scheduled(
                "rollup",datetime(2026,10,22,19,15,tzinfo=timezone.utc))
        self.assertEqual(result["status"],"rollup_already_reserved_or_sent")
        ledger.reserve.assert_not_called()
        ledger.mark_smtp_accepted.assert_not_called()


if __name__=="__main__":
    unittest.main()
