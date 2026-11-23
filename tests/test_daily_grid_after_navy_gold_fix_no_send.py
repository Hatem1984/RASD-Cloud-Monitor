"""Daily-only regression for the real 21-23 Nov Word layout transition.

All headlines, JPEGs, MIME headers, and ledger entries here are synthetic.
No SMTP, IMAP network access, secrets, private CAS, or production schedule.
This test deliberately lives outside the hourly PR.
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from docx import Document

from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx
from daily_sent_consolidator import consolidate_sent_words, extract_sent_originals
from monitor import article_id
from test_ministry_visual_daily_layout import MinistryMediaLayoutNoSend
from test_daily_sent_consolidation import (
    FakeSent, MergeActualDeliveredWord, SENDER, RECIPIENT,
)


class DailyGridAndLegacySentWord(unittest.TestCase):
    def new_2026_grid(self, root: Path, count: int = 2):
        report, source_digests = MinistryMediaLayoutNoSend()._report(root, count)
        # This matches the 21-23 November live *periodic* grid marker,
        # not the daily Word cover used by other layout tests.
        report.update({
            "title": "رصد | الفحص الدوري — نموذج منع التراجع فقط",
            "report_kind": "half_hourly",
            "report_period": "interval",
            "coverage": "HEALTHY",
            "ministry_media_grid": True,
            "sources": [{"feed_id": "offline-test", "status": "ok",
                         "verified_links": count}],
        })
        original_word = root / "RASD-News-With-Original-Screenshots.docx"
        render_docx(report, original_word)
        sources = [
            {
                "id": article_id(a["url"]),
                "headline": a["headline"],
                "source": a["source"],
                "url": a["url"],
                "published_at_cairo": a["published_at_cairo"],
                "published_display_cairo": a["published_display_cairo"],
                "publisher_excerpt": "عنصر صناعي لتجنب نقل أخبار حقيقية إلى GitHub",
            }
            for a in report["articles"]
        ]
        self.assertEqual(len(Document(original_word).inline_shapes), count)
        self.assertTrue(word_images_match_capture_digests(
            original_word, source_digests))
        return original_word, sources, source_digests

    def test_new_ministry_grid_extracts_correct_order_links_and_jpegs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            word, rows, receipts = self.new_2026_grid(root, 2)
            self.assertNotIn("الأخبار المطابقة",
                             [p.text.strip() for p in Document(word).paragraphs])
            (root / "verified").mkdir()
            collected = extract_sent_originals(
                word.read_bytes(), rows, root / "verified")
            self.assertEqual(len(collected), 2)
            self.assertEqual([a["id"] for a, _, _ in collected],
                             [a["id"] for a in rows])
            self.assertEqual([digest for _, _, digest in collected],
                             [r["sha256"] for r in receipts])
            self.assertEqual(len({a["url"] for a, _, _ in collected}), 2)

    def test_daily_consolidation_reads_new_grid_from_fake_readonly_sent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            word, stories, receipts = self.new_2026_grid(root, 2)
            msgid = "<rasd-" + "f"*24 + "@gmail.com>"
            fake_sent = FakeSent({
                msgid: MergeActualDeliveredWord().mail(
                    msgid, word.read_bytes())})
            state = {"entries": {
                news["id"]: {
                    "kind": "interval_item", "status": "smtp_accepted",
                    "news": news, "message_id": msgid,
                } for news in stories
            }}
            built, proof = consolidate_sent_words(
                stories, state, root / "daily",
                sender=SENDER, recipient=RECIPIENT,
                app_password="offline-only",
                start="22:00 اليوم السابق", end="22:00 اليوم",
                title="رصد | التجميع اليومي — فحص معزول فقط",
                config={"feeds": [{"id": "test-only"}]},
                client_factory=lambda: fake_sent)
            self.assertEqual(len(Document(built).inline_shapes), 2)
            self.assertEqual([a["sha256"] for a in proof],
                             [a["sha256"] for a in receipts])
            self.assertTrue(word_images_match_capture_digests(built, proof))
            self.assertTrue(fake_sent.selected_readonly)
            self.assertEqual(fake_sent.searched, [msgid])

    def test_prior_paragraph_style_still_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = MergeActualDeliveredWord()
            stories = [fixture.source_news(1)]
            old_word, hashes = fixture.sample_doc(root, stories)
            self.assertEqual(len(Document(root / ("interval-" + stories[0]["id"] + ".docx")).tables), 0)
            parsed = extract_sent_originals(old_word, stories, root)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0][2], hashes[stories[0]["id"]])

    def test_tampered_news_title_is_held_before_consolidation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            word, stories, _ = self.new_2026_grid(root, 1)
            fake_story = {**stories[0], "headline": "عنوان مختلف غير موجود"}
            (root / "bad").mkdir()
            with self.assertRaisesRegex(
                    RuntimeError, "daily_sent_grid_article_identity_hold"):
                extract_sent_originals(
                    word.read_bytes(), [fake_story], root / "bad")


if __name__ == "__main__":
    unittest.main()
