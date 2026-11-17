"""No-network evidence-grounded descriptive topic analysis, never inference."""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx
from rasd_ministry_visual_layout import descriptive_topic_counts
from test_ministry_visual_daily_layout import MinistryMediaLayoutNoSend


class MinistryTopicAnalysis(unittest.TestCase):
    def test_multiple_topics_from_exact_publisher_words_not_unique_events(self):
        entries = [
            {"headline": "الوزارة تبحث تمويل الشركات الناشئة والقطاع الخاص"},
            {"headline": "معهد التخطيط يناقش الذكاء الاصطناعى وتأثير التكنولوجيا"},
            {"headline": "وزارة التخطيط تعلن لقاءً مع المحافظين"},
        ]
        counted = descriptive_topic_counts(entries)
        self.assertEqual(counted["ريادة الأعمال والشركات الناشئة"], 1)
        self.assertEqual(counted["الاستثمار والقطاع الخاص"], 1)
        self.assertEqual(counted["الشراكات والتمويل"], 1)
        self.assertEqual(counted["التحول الرقمي والمعرفة"], 1)
        self.assertEqual(counted["متابعات أخرى غير مصنفة"], 1)
        self.assertGreater(sum(counted.values()), len(entries))
        self.assertNotIn("إيجابي", counted)
        self.assertNotIn("سلبي", counted)

    def test_arabic_diacritics_and_alef_variants_preserve_topic(self):
        entries = [{
            "headline": "تقرير عن الذَّكاء الإصطناعى والتحول الرقمي",
            "publisher_excerpt": "الاستثمار في الابتكار"
        }]
        counted = descriptive_topic_counts(entries)
        self.assertEqual(counted["التحول الرقمي والمعرفة"], 1)
        self.assertEqual(counted["الاستثمار والقطاع الخاص"], 1)

    def test_real_docx_path_adds_text_only_not_fake_pictures(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            report, receipts = MinistryMediaLayoutNoSend()._report(folder, 2)
            report["articles"][0]["headline"] = (
                "وزير التخطيط يبحث تمويل الشركات الناشئة")
            report["articles"][1]["headline"] = (
                "معهد التخطيط يناقش الذكاء الاصطناعي")
            path = folder / "ministry-categorized.docx"
            render_docx(report, path)
            doc = Document(path)
            text = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("المحاور الموضوعية — تحليل وصفي", text)
            self.assertIn("ريادة الأعمال والشركات الناشئة: 1 تغطية", text)
            self.assertIn("التحول الرقمي والمعرفة: 1 تغطية", text)
            self.assertIn("قد تنتمي التغطية لأكثر من محور", text)
            self.assertEqual(len(doc.inline_shapes), 2)
            self.assertTrue(word_images_match_capture_digests(path, receipts))

    def test_empty_topics_and_malformed_excerpt_do_not_invent_news(self):
        self.assertEqual(descriptive_topic_counts([]), {})
        counted = descriptive_topic_counts([{
            "headline": "", "publisher_excerpt": None
        }])
        self.assertEqual(counted["متابعات أخرى غير مصنفة"], 1)


if __name__ == "__main__":
    unittest.main()
