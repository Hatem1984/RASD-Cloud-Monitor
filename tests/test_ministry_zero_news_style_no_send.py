"""Daily zero-accepted-news report uses RASD ministry style without fabricated news.

Fully offline. The existing scheduled/CAS/SMTP mock test separately covers
one delivery reservation, mail status, and no duplicates.
"""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from daily_report import render_docx


class ZeroNewsMinistryStyle(unittest.TestCase):
    def sample(self):
        return {
            "title": "مآل | تقرير حالة المتابعة: لا أخبار مصوّرة مُسلّمة",
            "ministry_media_grid": True,
            "coverage": "NO_ACCEPTED_VERIFIED_NEWS",
            "display_window_start": "15 نوفمبر 2026 22:00",
            "display_window_end": "16 نوفمبر 2026 22:00",
            "articles": [],
            "sources": [],
            "verified_links": 0,
            "limitations": (
                "هذا تقرير حالة تشغيل وليس تقرير تغطية صحفية كاملة. "
                "لا يثبت عدم نشر أخبار خلال الفترة."
            ),
        }

    def test_zero_news_has_same_ministry_navy_cover_and_no_fake_photos(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "status.docx"
            render_docx(self.sample(), output)
            self.assertTrue(output.is_file())
            doc = Document(output)
            self.assertEqual(len(doc.inline_shapes), 0)
            self.assertGreaterEqual(len(doc.tables), 1)
            self.assertIn("تقرير رصد", doc.tables[0].cell(0, 0).text)
            self.assertIn("المواقع الإلكترونية", doc.tables[0].cell(0, 0).text)
            alltext = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("لا أخبار مصوّرة مُسلّمة", alltext)
            self.assertIn("ليس تقرير تغطية صحفية كاملة", alltext)
            self.assertIn("لا يثبت عدم نشر أخبار", alltext)
            self.assertTrue(output.stat().st_size >= 3000)

    def test_never_downgrade_nonempty_or_untrusted_article_to_zero_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "hold.docx"
            for change in (
                {"articles": [{"headline": "fake"}]},
                {"verified_links": 2},
                {"coverage": "HEALTHY"},
            ):
                with self.subTest(change=change):
                    invalid = {**self.sample(), **change}
                    with self.assertRaises((ValueError, KeyError)):
                        render_docx(invalid, dest)
                    self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
