"""Batched daily Word stress: 168 exact publisher JPEGs, no network or SMTP."""
from __future__ import annotations
import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from docx import Document

from daily_report import render_docx
from cloud_proof_report import word_images_match_capture_digests
from daily_sent_consolidator import MAX_DAILY_WORD_BYTES
from scheduled_rasd import MAX_ROLLUP


class DailyReportLargeCapacityNoSend(unittest.TestCase):
    def test_complete_168_original_image_word_keeps_every_original_digest(self):
        self.assertGreaterEqual(MAX_ROLLUP, 168)
        self.assertGreaterEqual(MAX_DAILY_WORD_BYTES, 15_000_000)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            articles, proofs = [], []
            for i in range(168):
                picture = root / f"original-{i:03d}.jpg"
                im = Image.new("RGB", (600, 450), "white")
                ink = ImageDraw.Draw(im)
                ink.rectangle((0, 0, 599, 75), fill=(11, 34, 71))
                ink.rectangle((40, 100, 550, 150), fill=(
                    20 + (i % 10) * 17, 45, 90))
                for y in range(165, 445, 35):
                    ink.rectangle((20, y, 570-(i % 8)*20, y+11),
                                  fill=(52, 98, 155))
                ink.text((20, 18), str(i), fill="white")
                im.save(picture, "JPEG", quality=84)
                articles.append({
                    "headline": f"وزارة التخطيط — صورة اختبار أصلية رقم {i+1}",
                    "source": "Hapi native news RSS",
                    "url": f"https://hapijournal.com/qa-original-{i}",
                    "publisher_excerpt": "عينة صناعية محلية",
                    "published_at_cairo": "2026-11-20 15:30 EET",
                    "published_display_cairo": "20 نوفمبر 2026",
                    "evidence_image_path": str(picture),
                })
                proofs.append({
                    "status": "verified",
                    "sha256": hashlib.sha256(picture.read_bytes()).hexdigest()})
            report = {
                "title": "رصد | التقرير المجمع الكامل — اختبار 168 صورة",
                "display_window_start": "19 نوفمبر 2026 22:00",
                "display_window_end": "20 نوفمبر 2026 22:00",
                "ministry_media_grid": True,
                "coverage": "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS",
                "verified_links": 168,
                "articles": articles,
                "sources": [], "limitations": "صور صناعية فقط",
            }
            final_path = root / "daily-168-no-send.docx"
            render_docx(report, final_path)
            self.assertTrue(final_path.exists())
            self.assertLessEqual(final_path.stat().st_size,
                                 MAX_DAILY_WORD_BYTES)
            doc = Document(final_path)
            self.assertEqual(len(doc.inline_shapes), 168)
            self.assertTrue(word_images_match_capture_digests(
                final_path, proofs))

    def test_181_image_daily_word_holds_instead_of_silent_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)
            im=Image.new("RGB", (500, 400), "white")
            sample=p/"test.jpg"
            im.save(sample,"JPEG")
            articles=[{
                "headline":f"خبر مصطنع {i}", "source":"Hapi native news RSS",
                "url":f"https://hapijournal.com/qa-{i}",
                "evidence_image_path":str(sample)}
                for i in range(181)]
            report={
                "title":"test", "display_window_start":"a",
                "display_window_end":"b",
                "ministry_media_grid":True,
                "coverage":"CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS",
                "verified_links":181,"articles":articles}
            target=p/"must-hold.docx"
            with self.assertRaisesRegex(ValueError,
                                        "rasd_visual_invalid_article_count"):
                render_docx(report,target)
            self.assertFalse(target.exists())


if __name__=="__main__":
    unittest.main()
