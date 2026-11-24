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
from PIL import Image, ImageDraw
from scheduled_rasd import safe_scheduled_hold_reason

from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx
from daily_sent_consolidator import consolidate_sent_words, extract_sent_originals
from monitor import article_id
from test_ministry_visual_daily_layout import MinistryMediaLayoutNoSend
from test_daily_sent_consolidation import (
    FakeSent, MergeActualDeliveredWord, SENDER, RECIPIENT,
)


class DailyGridAndLegacySentWord(unittest.TestCase):
    def new_2026_grid(self, root: Path, count: int = 2, *, sparse: str = ""):
        report, source_digests = MinistryMediaLayoutNoSend()._report(root, count)
        if sparse:
            path = Path(report["articles"][0]["evidence_image_path"])
            image = Image.new("RGB", (800, 500), "white")
            if sparse == "readable":
                draw = ImageDraw.Draw(image)
                draw.rectangle((0, 0, 799, 80), fill=(15, 32, 65))
                draw.rectangle((30, 120, 740, 145), fill=(33, 48, 74))
            image.save(path, "JPEG", quality=20, optimize=True)
            if sparse == "readable":
                self.assertGreaterEqual(path.stat().st_size, 3000)
                self.assertLess(path.stat().st_size, 8000)
            else:
                self.assertLess(path.stat().st_size, 3000)
            source_digests[0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
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

    def test_readable_sparse_jpeg_accepted_by_capture_is_preserved_in_daily_word(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            word, rows, receipts = self.new_2026_grid(root, 1, sparse="readable")
            (root / "verified").mkdir()
            collected = extract_sent_originals(word.read_bytes(), rows, root / "verified")
            self.assertEqual(collected[0][2], receipts[0]["sha256"])
            self.assertLess(Path(collected[0][1]).stat().st_size, 8000)

    def test_tiny_blank_jpeg_remains_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            word, rows, _ = self.new_2026_grid(root, 1, sparse="blank")
            (root / "bad").mkdir()
            with self.assertRaisesRegex(RuntimeError, "daily_sent_grid_original_jpeg_hold"):
                extract_sent_originals(word.read_bytes(), rows, root / "bad")

    def test_daily_diagnostics_allow_only_fixed_codes(self):
        for code in ("daily_sent_original_headlines_hold",
                     "daily_sent_grid_article_identity_hold",
                     "daily_sent_grid_original_jpeg_hold",
                     "daily_imap_archive_unavailable_hold"):
            self.assertEqual(safe_scheduled_hold_reason(RuntimeError(code)), code)
        self.assertEqual(safe_scheduled_hold_reason(RuntimeError(
            "daily_sent_grid_original_jpeg_hold: private message data")),
            "other_held_failure")

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
