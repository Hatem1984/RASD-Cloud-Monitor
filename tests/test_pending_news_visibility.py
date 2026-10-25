"""A pending RSS candidate is named and linked in Word, never counted as photographed news."""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from daily_report import render_docx


class PendingNewsVisibility(unittest.TestCase):
    def test_word_lists_capture_hold_without_fake_image_or_delivery(self):
        url = "https://hapijournal.com/public-ministry-example"
        report = {
            "title": "رصد | تقرير حالة متابعة", "display_window_start": "١٩:٣٠",
            "display_window_end": "١٩:٣٧",
            "coverage": "ORIGINAL_IMAGE_HOLD_NO_VERIFIED_DELIVERY",
            "verified_links": 1, "articles": [], "sources": [],
            "scope_note": "14 مصدر RSS فعال من 50 مصدر بحثي",
            "limitations": "مادة معلقة لا تعد خبرًا مسلّمًا.",
            "held_candidates": [{
                "headline": "وزارة التخطيط تعلن متابعة المشروعات",
                "source": "Hapi native news RSS",
                "url": url,
                "published_display_cairo": "٢٥ أكتوبر ٢٠٢٦",
                "reason": "publisher_access_refused",
            }],
        }
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder) / "status.docx"
            render_docx(report, filename)
            word = Document(filename)
            text = "\n".join(p.text for p in word.paragraphs)
            self.assertIn("مواد اكتُشفت لكنها معلّقة", text)
            self.assertIn("وزارة التخطيط تعلن متابعة المشروعات", text)
            self.assertIn("publisher_access_refused", text)
            self.assertIn("14 مصدر RSS فعال", text)
            self.assertNotIn("لقطة موثقة من صفحة الناشر الأصلية", text)
            self.assertEqual(len(word.inline_shapes), 0)
            self.assertTrue(any(rel.target_ref == url
                                for rel in word.part.rels.values()
                                if rel.reltype.endswith("/hyperlink")))


if __name__ == "__main__":
    unittest.main()
