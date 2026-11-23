"""Production 22:00 bulletin reuses ORIGINAL SENT Word, never publisher recapture."""
from datetime import datetime, timezone
import os
import io
import contextlib
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import scheduled_rasd as worker
import daily_sent_consolidator as archive


class ProductionNightlyOneWord(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {"RASD_DAILY_SENT_ARCHIVE_ENABLED": "true",
             "RASD_JOB_CRON": worker.DAILY_CRON,
             "GITHUB_EVENT_NAME": "schedule"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def mock_accepted_news(self):
        return [{
            "id": "a"*24,
            "headline": "وزير التخطيط يستعرض توجهات الإصلاح",
            "source": "Alborsa native Egyptian Economy RSS",
            "url": "https://www.alborsaanews.com/2026/10/23/2001360",
            "published_at_cairo": "2026-10-23 12:00 EEST",
            "published_display_cairo": "23 أكتوبر 2026",
            "publisher_excerpt": "خبر منشور",
        }]

    def test_daily_uses_sent_word_snapshots_and_one_smtp_receipt(self):
        ledger=MagicMock()
        state={"entries":{}}
        ledger.read.return_value=(state,"sha")
        ledger.reserve.return_value="reserved"
        items=self.mock_accepted_news()
        def consolidate(*args,**kwargs):
            self.assertEqual(args[0],items)
            self.assertIs(args[1],state)
            self.assertEqual(kwargs["sender"],"sender@gmail.com")
            self.assertEqual(kwargs["recipient"],"approved@example.com")
            self.assertEqual(kwargs["app_password"],"fake-password")
            filename=Path(args[2])/"real-original-daily.docx"
            filename.write_bytes(b"offline-only")
            return filename,[{"sha256":"a"*64,"status":"verified"}]
        with (
            patch.object(worker,"require_github_scheduler"),
            patch.object(worker,"scheduled_phase",return_value="rollup"),
            patch.object(worker,"protected_credentials",
                         return_value=("sender@gmail.com","approved@example.com",
                                       "fake-password",ledger)),
            patch.object(worker,"news_for_rollup",return_value=items),
            patch.object(archive,"consolidate_sent_words",
                         side_effect=consolidate) as merged,
            patch.object(worker,"prepare_word") as recapture,
            patch.object(worker,"send_one_word",
                         return_value="<rasd-offline-daily@gmail.com>") as smtp,
        ):
            result=worker.run_scheduled(
                "rollup",datetime(2026,10,24,19,10,tzinfo=timezone.utc))
        self.assertEqual(result["items"],1)
        self.assertEqual(result["status"],"daily_smtp_accepted_unconfirmed_inbox")
        merged.assert_called_once()
        recapture.assert_not_called()
        smtp.assert_called_once()
        ledger.reserve.assert_called_once()
        ledger.mark_smtp_accepted.assert_called_once()

    def test_nov21_nov22_real_count_shaped_archive_hold_is_explicit_and_never_reserved(self):
        # The private read-only ledger had 8 and 2 accepted article records
        # for these cutoff dates; ONLY synthetic story payloads are used here.
        # No production credentials, private CAS data or actual e-mail IDs.
        for iso_day, n in [("2026-11-21", 8), ("2026-11-22", 2)]:
            with self.subTest(day=iso_day):
                ledger = MagicMock()
                ledger.read.return_value = ({"entries": {}}, "sha")
                synthetic = [
                    {**self.mock_accepted_news()[0],
                     "id": f"{i+1:024x}",
                     "url": f"https://www.alborsaanews.com/example-{i+1}",
                     "headline": f"خبر صناعي مؤهل رقم {i+1}"}
                    for i in range(n)
                ]
                output = io.StringIO()
                with (
                    patch.object(worker, "require_github_scheduler"),
                    patch.object(worker, "protected_credentials",
                        return_value=("sender@gmail.com","approved@example.com",
                                      "not-a-real-password",ledger)),
                    patch.object(worker, "news_for_rollup", return_value=synthetic),
                    patch.object(archive, "consolidate_sent_words",
                        side_effect=RuntimeError("daily_sent_message_not_found")),
                    patch.object(worker, "send_one_word") as send,
                    contextlib.redirect_stdout(output),
                ):
                    with self.assertRaisesRegex(
                            RuntimeError, "daily_sent_message_not_found"):
                        worker.run_scheduled(
                            "rollup", datetime.fromisoformat(
                                iso_day + "T20:00:15+00:00"))
                diagnostic = [
                    json.loads(s.partition("=")[2])
                    for s in output.getvalue().splitlines()
                    if s.startswith("RASD_DAILY_STAGE=")
                ]
                self.assertTrue(diagnostic)
                self.assertIn("reading_original_sent_word",
                              [z["stage"] for z in diagnostic])
                self.assertNotIn("word_ready_cas_next",
                                 [z["stage"] for z in diagnostic])
                self.assertTrue(all(z["cairo_day"] == iso_day for z in diagnostic))
                self.assertTrue(all(len(z["delivery_hint"]) == 8
                                    for z in diagnostic))
                ledger.reserve.assert_not_called()
                ledger.mark_smtp_accepted.assert_not_called()
                send.assert_not_called()
                self.assertEqual(worker.safe_scheduled_hold_reason(
                    RuntimeError("daily_sent_message_not_found")),
                    "daily_sent_message_not_found")

    def test_if_original_sent_mail_archive_unavailable_no_daily_email(self):
        ledger=MagicMock()
        ledger.read.return_value=({"entries":{}},"sha")
        with (
            patch.object(worker,"require_github_scheduler"),
            patch.object(worker,"scheduled_phase",return_value="rollup"),
            patch.object(worker,"protected_credentials",
                         return_value=("sender@gmail.com","approved@example.com",
                                       "fake-password",ledger)),
            patch.object(worker,"news_for_rollup",
                         return_value=self.mock_accepted_news()),
            patch.object(archive,"consolidate_sent_words",
                         side_effect=RuntimeError("daily_imap_archive_unavailable_hold")),
            patch.object(worker,"prepare_word") as recapture,
            patch.object(worker,"send_one_word") as smtp,
        ):
            with self.assertRaisesRegex(
                RuntimeError,"daily_imap_archive_unavailable_hold"):
                worker.run_scheduled("rollup",datetime(
                    2026,10,24,19,10,tzinfo=timezone.utc))
        recapture.assert_not_called()
        smtp.assert_not_called()
        ledger.reserve.assert_not_called()
        ledger.mark_smtp_accepted.assert_not_called()


if __name__=="__main__":
    unittest.main()
