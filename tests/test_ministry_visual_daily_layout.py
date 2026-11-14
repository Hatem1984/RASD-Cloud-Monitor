"""No-network acceptance for the 1-Nov-style RASD daily original-media Word.

All photos and headlines here are synthetic. No source, SMTP or private
ledger I/O is possible; production acceptance still requires live proof.
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw

from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx


class MinistryMediaLayoutNoSend(unittest.TestCase):
    def _report(self, folder: Path, count: int = 4) -> tuple[dict, list[dict]]:
        articles, receipts = [], []
        publishers = [
            "Hapi native news RSS",
            "Al Masry Al Youm native news RSS",
            "Al Shorouk native Economy RSS",
            "Masrawy native Egypt news RSS",
        ]
        for i in range(count):
            image = folder / f"original-test-{i}.jpg"
            picture = Image.new("RGB", (1200, 900), "white")
            ink = ImageDraw.Draw(picture)
            ink.rectangle((0, 0, 1199, 150), fill=(12, 32, 71))
            ink.rectangle((100, 220, 1000, 270), fill=(96+i*15, 42, 64))
            ink.rectangle((100, 300, 850, 725), fill=(72, 105+i*15, 138))
            picture.save(image, format="JPEG", quality=88)
            articles.append({
                "headline": f"وزارة التخطيط — نموذج مؤقت للخبر رقم {i+1} (غير حقيقي)",
                "source": publishers[i % len(publishers)],
                "url": f"https://hapijournal.com/offline-fixture-{i}",
                "evidence_image_path": str(image),
                "published_at_cairo": "2026-11-14 12:00 EET",
                "published_display_cairo": "14 نوفمبر 2026",
            })
            receipts.append({
                "status": "verified",
                "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            })
        report = {
            "ministry_media_grid": True,
            "coverage": "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS",
            "title": "رصد | التقرير المجمع الحقيقي — عينة غير إنتاجية",
            "display_window_start": "13 نوفمبر 2026 الساعة 22:00",
            "display_window_end": "14 نوفمبر 2026 الساعة 22:00",
            "articles": articles,
            "verified_links": count,
            "sources": [],
            "limitations": "عينة مخصصة لاختبار التنسيق فقط وليس أخبارًا حقيقية.",
        }
        return report, receipts

    def test_cover_analysis_and_four_original_jpegs_with_exact_digests(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            report, receipts = self._report(folder)
            target = folder / "ministry-media.docx"
            render_docx(report, target)
            word = Document(target)
            self.assertTrue(target.is_file())
            self.assertEqual(len(word.inline_shapes), 4)
            self.assertGreaterEqual(len(word.tables), 3)
            self.assertTrue(word_images_match_capture_digests(target, receipts))
            paragraphs = "\n".join(p.text for p in word.paragraphs)
            self.assertIn("التقرير المجمع الحقيقي", paragraphs)
            self.assertIn(report["articles"][0]["headline"], paragraphs)
            self.assertIn("تحليل الرصد", paragraphs)
            tables = "\n".join(
                c.text for t in word.tables for row in t.rows for c in row.cells
            )
            self.assertIn("تقرير رصد", tables)
            self.assertIn("المواقع الإلكترونية", tables)
            self.assertIn("حابي", tables)
            self.assertIn("المصري اليوم", tables)
            self.assertEqual(len(word.inline_shapes), len(receipts))

    def test_reject_missing_image_and_non_archived_data(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            report, _ = self._report(folder, 1)
            report["articles"][0]["evidence_image_path"] = str(folder / "missing.jpg")
            with self.assertRaisesRegex(ValueError, "rasd_visual_missing_original_evidence"):
                render_docx(report, folder / "must-hold.docx")
            self.assertFalse((folder / "must-hold.docx").exists())
            report["coverage"] = "HEALTHY"
            with self.assertRaisesRegex(ValueError, "rasd_visual_layout_requires_accepted_sent_originals"):
                render_docx(report, folder / "still-hold.docx")

    def test_old_interval_layout_never_uses_new_media_renderer(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            report, _ = self._report(folder, 1)
            report["ministry_media_grid"] = False
            report["coverage"] = "HEALTHY"
            report["display_window_start"] = "2026-11-14 11:00"
            report["display_window_end"] = "2026-11-14 11:30"
            render_docx(report, folder / "existing-interval.docx")
            doc = Document(folder / "existing-interval.docx")
            self.assertEqual(len(doc.inline_shapes), 1)
            self.assertEqual(len(doc.tables), 0)


if __name__ == "__main__":
    unittest.main()
