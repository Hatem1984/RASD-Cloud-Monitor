"""Offline tests: real prior article + blocked re-capture must NOT disappear."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from docx import Document
from monitor import article_id
import scheduled_rasd as worker


class PreviouslyAcceptedImageHold(unittest.TestCase):
    def setUp(self):
        # Only this offline fixture emulates a genuinely scheduled worker.
        # Production event authentication remains strictly fail-closed.
        self._scheduled_env = patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule"})
        self._scheduled_env.start()
        self.addCleanup(self._scheduled_env.stop)

    def story(self):
        link = "https://hapijournal.com/verified-earlier"
        return {
            "id": article_id(link),
            "url": link,
            "source": "Hapi native news RSS",
            "headline": "وزارة التخطيط — خبر مصور سبق إرساله",
            "published_at_cairo": "2026-10-22 16:00 EEST",
            "published_display_cairo": "22 أكتوبر 2026",
            "publisher_excerpt": "مصدر صحفي أصلي",
        }

    def setup_context(self, *, failure="publisher_screenshot_hold"):
        ledger = MagicMock()
        ledger.read.return_value = ({"entries": {}}, "sha")
        ledger.reserve.return_value = "reserved"
        selected = [self.story()]
        return ledger, selected

    def test_original_publisher_blocked_at_rollup_emits_true_status_no_fake_image(self):
        ledger, rows = self.setup_context()
        outgoing = []
        def assert_status_attachment(doc, **kwargs):
            word = Document(doc)
            alltext = "\n".join(p.text for p in word.paragraphs)
            self.assertEqual(len(word.inline_shapes), 0)
            self.assertIn("أخبار مُرسلة وصورها غير متاحة", alltext)
            self.assertIn(rows[0]["headline"], alltext)
            self.assertIn("لا نختلق صورًا", alltext)
            self.assertIn("ليس تقريرًا", kwargs["body_text"])
            outgoing.append(kwargs)
            return "<rasd-status-only@gmail.com>"

        with patch.object(worker, "require_github_scheduler"), \
             patch.object(worker, "scheduled_phase", return_value="rollup"), \
             patch.object(worker, "protected_credentials", return_value=(
                 "source-sender@gmail.com", "approved@example.com",
                 "test-password", ledger)), \
             patch.object(worker, "news_for_rollup", return_value=rows), \
             patch.object(worker, "prepare_word", side_effect=RuntimeError(
                 "publisher_screenshot_hold")), \
             patch.object(worker, "send_one_word",
                          side_effect=assert_status_attachment):
            result = worker.run_scheduled(
                "rollup", datetime(2026, 10, 22, 19, 4,
                                   tzinfo=timezone.utc))

        self.assertEqual(len(outgoing), 1)
        self.assertEqual(result["items"], 1)
        self.assertTrue(result["is_explicit_image_capture_hold_notice"])
        self.assertFalse(result["is_explicit_zero_accepted_news_notice"])
        self.assertEqual(ledger.reserve.call_count, 1)
        self.assertEqual(ledger.mark_smtp_accepted.call_count, 1)

    def test_word_integrity_failure_is_never_downgraded_to_status(self):
        ledger, rows = self.setup_context()
        with patch.object(worker, "require_github_scheduler"), \
             patch.object(worker, "scheduled_phase", return_value="rollup"), \
             patch.object(worker, "protected_credentials", return_value=(
                 "source-sender@gmail.com", "approved@example.com",
                 "test-password", ledger)), \
             patch.object(worker, "news_for_rollup", return_value=rows), \
             patch.object(worker, "prepare_word", side_effect=RuntimeError(
                 "word_screenshot_identity_hold")), \
             patch.object(worker, "send_one_word",
                          side_effect=AssertionError("mail must not be sent")):
            with self.assertRaisesRegex(RuntimeError,
                                         "word_screenshot_identity_hold"):
                worker.run_scheduled(
                    "rollup", datetime(2026, 10, 22, 19, 4,
                                       tzinfo=timezone.utc))
        ledger.reserve.assert_not_called()
        ledger.mark_smtp_accepted.assert_not_called()


if __name__ == "__main__":
    unittest.main()
