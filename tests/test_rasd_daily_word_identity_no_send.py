"""Offline: Ministry report never inherits the unrelated legacy SMTP brand.

Transport title, recipient, CC, Message-ID, CAS and SMTP remain unchanged.
"""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from daily_report import render_docx
from cloud_proof_report import word_images_match_capture_digests
from test_ministry_visual_daily_layout import MinistryMediaLayoutNoSend


class RASDWordOnlyIdentity(unittest.TestCase):
    def test_formatted_ministry_daily_word_hides_legacy_mail_subject_brand(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            report, evidence = MinistryMediaLayoutNoSend()._report(folder, 2)
            report["title"] = "مآل | التقرير المجمع للأخبار المرسلة | ١٧ نوفمبر ٢٠٢٦"
            unchanged_transport_subject = report["title"]
            path = folder / "rasd-word.docx"
            render_docx(report, path)
            doc = Document(path)
            text = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("رصد | التقرير المجمع للأخبار المرسلة", text)
            self.assertNotIn("مآل", text)
            self.assertEqual(report["title"], unchanged_transport_subject)
            self.assertEqual(len(doc.inline_shapes), 2)
            self.assertTrue(word_images_match_capture_digests(path, evidence))

    def test_nonlegacy_rasd_title_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            report, _ = MinistryMediaLayoutNoSend()._report(folder, 1)
            report["title"] = "رصد | عنوان التقرير المعتمد"
            path = folder / "rasd-verified.docx"
            render_docx(report, path)
            text = "\n".join(p.text for p in Document(path).paragraphs)
            self.assertIn(report["title"], text)


if __name__ == "__main__":
    unittest.main()
