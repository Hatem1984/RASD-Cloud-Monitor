"""Production-shaped delivery test with 2 genuine-clipping identities, NO SMTP.

The images and emails are mocked. This tests how many publisher coverages
reach the existing original screenshot gate; it does NOT prove live evidence.
"""
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import scheduled_rasd as worker

HEADING = ("وزارة التخطيط تستهدف تخفيض الدين الخارجي وتعزيز "
           "الاستثمارات الأجنبية خلال العام")


class PublisherCoverageIntervalNoSend(unittest.TestCase):
    def test_different_publisher_same_event_reach_one_word_not_two_messages(self):
        news = [
            {"id": char*24, "source": name, "headline": HEADING,
             "published_at_cairo": "2026-11-17 10:30 EET",
             "url": "https://" + host + "/original/" + char}
            for char, name, host in (
                ("a", "مصدر مستقل أول", "one.example"),
                ("b", "مصدر مستقل ثان", "two.example"),
            )
        ]
        ledger = MagicMock()
        ledger.read.return_value = ({"entries": {}}, "fixture-sha")
        encountered = []

        def prepare(items, config, output, **kwargs):
            encountered.extend(items)
            filename = Path(output) / "synthetic-not-actual.docx"
            filename.write_bytes(b"offline mock")
            return filename, list(items), 0, False

        with (
            patch.dict(os.environ, {
                "GITHUB_EVENT_NAME": "schedule",
                "RASD_JOB_CRON": worker.HALF_HOUR_CRON,
            }),
            patch.object(worker, "require_github_scheduler"),
            patch.object(worker, "scheduled_phase", return_value="interval"),
            patch.object(worker, "protected_credentials",
                         return_value=("sender@example.invalid",
                                       "recipient@example.invalid",
                                       "offline", ledger)),
            patch.object(worker, "discover_interval_news", return_value=news),
            patch.object(worker, "prepare_source_limited_verified_word",
                         side_effect=prepare),
            patch.object(worker, "reserve_stories") as reserve,
            patch.object(worker, "send_one_word",
                         return_value="<synthetic@invalid.example>") as smtp,
        ):
            result = worker.run_scheduled(
                "interval", datetime(2026, 11, 17, 8, 35,
                                      tzinfo=timezone.utc))

        self.assertEqual(len(encountered), 2)
        self.assertEqual({x["source"] for x in encountered},
                         {"مصدر مستقل أول", "مصدر مستقل ثان"})
        self.assertEqual(result["items"], 2)
        reserve.assert_called_once()
        self.assertEqual(len(reserve.call_args.args[1]), 2)
        smtp.assert_called_once()
        ledger.mark_smtp_accepted_many.assert_called_once()

    def test_same_article_in_private_ledger_not_reprocessed(self):
        # The dedupe itself is pure; it has no private ledger or email calls.
        from event_identity import distinct_publisher_coverages
        original = {"id": "a"*24, "source": "صحيفة", "headline": HEADING,
                    "published_at_cairo": "2026-11-17 10:30 EET"}
        retained, held = distinct_publisher_coverages(
            [dict(original)], [dict(original)])
        self.assertEqual(retained, [])
        self.assertEqual(len(held), 1)


if __name__ == "__main__":
    unittest.main()
