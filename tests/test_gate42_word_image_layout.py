"""Word screenshot layout regression: protect against publisher full-page JPEG overflow.

The image data here is synthetic, NEVER a real publisher or acceptance proof.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from daily_report import render_docx


def fixture_image(path, width, height):
    im = Image.new("RGB", (width, height), "#ffffff")
    canvas = ImageDraw.Draw(im)
    for y in range(20, height-20, 65):
        canvas.rectangle((15, y, width - 15, min(y + 25, height-1)),
                         fill=(22, 60, 90))
    im.save(path, "JPEG", quality=88)


def minimal_report(pictures):
    return {
        "title": "رصد | اختبار تنسيق Word العربي — صور ناشر اصطناعية فقط",
        "display_window_start": "١٧ أكتوبر ٢٠٢٦",
        "display_window_end": "١٨ أكتوبر ٢٠٢٦",
        "coverage": "HEALTHY",
        "verified_links": len(pictures),
        "articles": [
            {
                "headline": "وزارة التخطيط تعلن متابعات اقتصادية " + str(i),
                "source": "وزارة التخطيط — الموقع الرسمي",
                "url": "https://mped.gov.eg/singlenews?id=" + str(i+7269) + "&lang=ar",
                "published_at_cairo": "2026-10-17",
                "published_display_cairo": "١٧ أكتوبر ٢٠٢٦ — اليوم فقط",
                "evidence_image_path": str(p),
                "publisher_excerpt": "",
            }
            for i, p in enumerate(pictures)
        ],
        "sources": [
            {"feed_id": "mped-official", "status": "ok",
             "verified_links": len(pictures), "error_type": None}
        ],
        "limitations": "هذا نموذج اختبار غير إنتاجي.",
    }


class PublisherScreenshotWordBounds(unittest.TestCase):
    def test_portrait_full_page_and_wide_publisher_jpegs_are_not_clipped(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            portrait = folder / "full-page.jpg"
            wide = folder / "viewport.jpg"
            fixture_image(portrait, 1200, 4800)
            fixture_image(wide, 1200, 900)
            output = folder / "report.docx"
            render_docx(minimal_report([portrait, wide]), output)
            doc = Document(output)
            self.assertEqual(len(doc.inline_shapes), 2)
            for original, shape in zip((portrait, wide), doc.inline_shapes):
                self.assertLessEqual(shape.width, Inches(5.6) + 2000)
                self.assertLessEqual(shape.height, Inches(6.2) + 2000)
                self.assertGreater(shape.width, Inches(1.0))
                with Image.open(original) as im:
                    px_ratio = im.height / im.width
                word_ratio = shape.height / shape.width
                self.assertAlmostEqual(word_ratio, px_ratio, delta=0.012)
            picture_paragraphs = [
                p for p in doc.paragraphs if p._p.xpath(".//wp:inline")
            ]
            self.assertEqual(len(picture_paragraphs), 2)
            for paragraph in picture_paragraphs:
                self.assertEqual(paragraph.alignment, WD_ALIGN_PARAGRAPH.CENTER)
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 5000)

    def test_original_images_are_not_reencoded_when_added_to_word(self):
        import hashlib
        from zipfile import ZipFile
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            original = folder / "original.jpg"
            fixture_image(original, 900, 4100)
            word = folder / "proof.docx"
            render_docx(minimal_report([original]), word)
            digest = hashlib.sha256(original.read_bytes()).hexdigest()
            with ZipFile(word) as archive:
                images = [
                    archive.read(name) for name in archive.namelist()
                    if name.startswith("word/media/")
                ]
            self.assertEqual(len(images), 1)
            self.assertEqual(hashlib.sha256(images[0]).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
