"""MAAL public naming without rewriting private RASD transport or historical evidence.

Offline; never sends mail, changes idempotency ledger or opens original websites.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from docx import Document
from daily_report import render_docx


class MaalBrandTransition(unittest.TestCase):
    def test_all_current_scheduled_subjects_use_maal(self):
        s = Path("scheduled_rasd.py").read_text(encoding="utf-8")
        self.assertNotIn("رصد |", s)
        self.assertIn("مآل | أخبار جديدة من الفحص الدوري", s)
        self.assertIn("مآل | التقرير المجمع للأخبار المرسلة", s)
        self.assertIn("مآل | تقرير حالة المتابعة النصف ساعية", s)
        self.assertIn("تقرير مآل للمتابعة والتحليل", s)

    def test_report_word_contains_new_brand_without_fake_evidence(self):
        report = {
            "title": "مآل | تقرير حالة المتابعة",
            "display_window_start": "٢٦ أكتوبر الساعة ١٤:٠٠",
            "display_window_end": "٢٦ أكتوبر الساعة ١٤:٣٠",
            "coverage": "NO_VERIFIED_NEW_DELIVERY",
            "verified_links": 13, "articles": [], "sources": [],
            "limitations": "لا يتم اختلاق أخبار أو صور عند عدم وجود دليل.",
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "MAAL-Report.docx"
            render_docx(report, path)
            doc = Document(path)
            self.assertIn("مآل | تقرير حالة المتابعة", doc.paragraphs[0].text)
            self.assertEqual(len(doc.inline_shapes), 0)

    def test_brand_not_applied_to_private_cas_or_gmail_headers(self):
        delivery = Path("scheduled_rasd.py").read_text(encoding="utf-8")
        archive = Path("daily_sent_consolidator.py").read_text(encoding="utf-8")
        self.assertIn("X-RASD-Delivery-ID", delivery)
        self.assertIn('f"<rasd-{key}@gmail.com>"', delivery)
        self.assertIn("X-RASD-Delivery-ID", archive)
        self.assertIn("RASD_REPORT_CC", delivery)
        self.assertIn("APPROVED_REPORT_COPY_SHA256", delivery)


if __name__ == "__main__":
    unittest.main()
