"""Review-visible RASD Word quality, offline. No live posts, mail or credentials."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from PIL import Image

from daily_report import display_rss_excerpt, render_docx


class RasdWordVisibleQualityTests(unittest.TestCase):
    def test_source_specific_duplicate_footer_only_is_removed(self):
        title = "لقاء وزير التخطيط"
        source = "Sada El Balad native news RSS"
        text = "استقبل الوزير وفداً من الخارج صدى البلد : المصدر " + title
        self.assertEqual(
            display_rss_excerpt(text, title, source),
            "استقبل الوزير وفداً من الخارج")
        ordinary = "صدر بيان تخطيطي جديد دون تذييل"
        self.assertEqual(display_rss_excerpt(ordinary, title, source), ordinary)
        self.assertEqual(
            display_rss_excerpt(text, title + " آخر", source), text)

    def test_wordpress_footer_removed_without_changing_report_evidence(self):
        raw = ("عقد المعهد الحلقة الثانية، بحضور باحثين […] "
               "The post الحلقة الثانية appeared first on "
               "Institute of National Planning - معهد التخطيط القومي .")
        self.assertEqual(
            display_rss_excerpt(
                raw, "الحلقة الثانية", "National Planning Institute native RSS"),
            "عقد المعهد الحلقة الثانية، بحضور باحثين")

    def test_realistic_report_retains_original_image_link_date_and_discloses_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            image = folder / "publisher.jpeg"
            Image.new("RGB", (850, 1450), "white").save(image, "JPEG")
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            raw = ("تم عقد لقاء مع الوفد صدى البلد : المصدر "
                   "وزير التخطيط يلتقي الوفد")
            report = {
                "title": "رصد | أخبار جديدة من الفحص الدوري",
                "display_window_start": "٨ نوفمبر ٢٠٢٦، الساعة ٠٩:٣٠",
                "display_window_end": "٨ نوفمبر ٢٠٢٦، الساعة ٠٩:٣٧",
                "coverage": "SOURCE_LIMITED", "verified_links": 18,
                "articles": [{
                    "headline": "وزير التخطيط يلتقي الوفد",
                    "source": "Sada El Balad native news RSS",
                    "url": "https://www.elbalad.news/7172179",
                    "publisher_excerpt": raw,
                    "published_at_cairo": "2026-11-08 09:36 EET",
                    "published_display_cairo": "٨ نوفمبر ٢٠٢٦، الساعة ٠٩:٣٦",
                    "evidence_image_path": str(image),
                }],
                "sources": [
                    {"feed_id": "elbalad", "status": "ok", "verified_links": 18,
                     "error_type": None},
                    {"feed_id": "masrawy", "status": "failed", "verified_links": 0,
                     "error_type": "original_feed_unavailable"},
                ],
                "held_candidates": [{
                    "headline": "خبر معلّق",
                    "source": "Al Masry Al Youm native news RSS",
                    "reason": "other",
                    "url": "https://www.almasryalyoum.com/news/details/4403562",
                    "published_display_cairo": "٧ نوفمبر ٢٠٢٦، الساعة ١٢:٤٥",
                }],
                "limitations": "لم يثبت تحقق الصور المعلقة.",
            }
            path = folder / "review.docx"
            render_docx(report, path)
            doc = Document(path)
            body = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("رصد |", body)
            self.assertNotIn("مآل", body)
            self.assertIn("تم عقد لقاء مع الوفد", body)
            self.assertNotIn("صدى البلد : المصدر", body)
            self.assertNotIn("[other]", body)
            self.assertNotIn("original_feed_unavailable", body)
            self.assertIn("مصراوي", body)
            self.assertIn("صدى البلد: متاح", body)
            self.assertIn("المصدر: صدى البلد | النشر: ٨ نوفمبر ٢٠٢٦", body)
            self.assertIn("مصراوي: تعذّر الوصول", body)
            self.assertNotIn("ملاحظة تحريرية آلية", body)
            self.assertNotIn("تحليل تحريري مرتبط", body)
            self.assertEqual(doc.styles["Title"].font.size.pt, 11.5)
            self.assertLessEqual(doc.sections[0].top_margin.inches, 0.43)
            self.assertLessEqual(doc.sections[0].bottom_margin.inches, 0.35)
            self.assertEqual(len(doc.inline_shapes), 1)
            evidence_labels = [p for p in doc.paragraphs if
                               p.text == "لقطة موثقة من صفحة الناشر الأصلية"]
            self.assertEqual(len(evidence_labels), 1)
            self.assertTrue(evidence_labels[0].paragraph_format.keep_with_next)
            self.assertIn("https://www.elbalad.news/7172179", [
                r.target_ref for r in doc.part.rels.values()
                if r.reltype.endswith("/hyperlink")])
            with ZipFile(path) as output:
                embedded = {
                    hashlib.sha256(output.read(n)).hexdigest()
                    for n in output.namelist() if n.startswith("word/media/")
                }
            self.assertIn(digest, embedded)
            self.assertEqual(report["articles"][0]["publisher_excerpt"], raw)

    def test_consolidated_daily_has_no_orphan_source_section(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "daily.docx"
            render_docx({
                "title": "رصد | التقرير المجمع",
                "display_window_start": "أمس", "display_window_end": "اليوم",
                "coverage": "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS",
                "verified_links": 0,
                "articles": [], "sources": [], "limitations": "تقرير حالة.",
            }, path)
            doc = Document(path)
            self.assertNotIn("حالة المصادر",
                             [p.text.strip() for p in doc.paragraphs])


if __name__ == "__main__":
    unittest.main()
