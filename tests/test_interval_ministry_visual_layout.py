"""Offline regression: scheduled interval shares final ministry layout, not daily evidence semantics."""
import tempfile
import unittest
from pathlib import Path

from docx import Document

from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx
from test_ministry_visual_daily_layout import MinistryMediaLayoutNoSend


class IntervalSameFinalWordLayout(unittest.TestCase):
    def test_verified_interval_has_same_structure_and_original_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            daily, digests = MinistryMediaLayoutNoSend()._report(root, 2)
            final_path = root / "final.docx"
            render_docx(daily, final_path)
            interval = {
                **daily,
                "title": "رصد | تقرير المتابعة الساعي",
                "coverage": "SOURCE_LIMITED",
                "ministry_media_grid": True,
                "report_period": "interval",
                "report_kind": "half_hourly",
                "sources": [
                    {"feed_id": "hapi", "status": "ok", "verified_links": 1},
                    {"feed_id": "masrawy", "status": "failed", "verified_links": 0},
                ],
                "held_candidates": [{"headline": "خبر معلّق بدون صورة"}],
                "limitations": "تغطية جزئية: تعذر مصدر، والخبر المعلق لم يُرسل.",
            }
            interval_path = root / "hourly.docx"
            render_docx(interval, interval_path)
            final = Document(final_path)
            hourly = Document(interval_path)
            self.assertEqual(len(hourly.inline_shapes), 2)
            self.assertEqual(len(final.inline_shapes), 2)
            self.assertEqual(len(hourly.tables), len(final.tables))
            for doc in (hourly, final):
                section = doc.sections[0]
                printable = section.page_width - section.left_margin - section.right_margin
                summary = doc.tables[1]
                for row in summary.rows:
                    self.assertLessEqual(sum(c.width for c in row.cells), printable)
                    self.assertEqual([c.width for c in row.cells],
                                     [c.width for c in summary.columns])

            self.assertTrue(word_images_match_capture_digests(interval_path, digests))
            text = "\n".join(p.text for p in hourly.paragraphs)
            self.assertIn("تحليل الرصد", text)
            self.assertIn("توزيع التغطيات على المواقع", text)
            self.assertIn("حالة مصادر الرصد: 1 متاح من 2", text)
            self.assertIn("مواد مطابقة معلّقة ولم تُسلّم: 1", text)
            self.assertNotIn("سبق إرسالها", text)
            self.assertNotIn("وفق سجل التسليم فقط", text)
            self.assertIn("تقرير المتابعة النصف ساعية", hourly.tables[0].cell(0, 0).text)

    def test_hourly_uses_same_daily_cover_and_original_cards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            daily, digests = MinistryMediaLayoutNoSend()._report(root, 7)
            labeled = [dict(article, hourly_publication_bucket="within_previous_hour")
                       for article in daily["articles"]]
            hourly = {**daily, "articles": labeled,
                      "hourly_in_period": 7, "hourly_recovered": 0,
                      "title": "رصد | تقرير المتابعة الساعية",
                      "report_period": "interval", "report_kind": "hourly",
                      "ministry_media_grid": True, "coverage": "HEALTHY",
                      "sources": [{"feed_id": "hapi", "status": "ok",
                                   "verified_links": 7}]}
            output = root / "hourly-seven.docx"
            render_docx(hourly, output)
            word = Document(output)
            self.assertIn("تقرير المتابعة الساعية",
                          word.tables[0].cell(0, 0).text)
            self.assertEqual(len(word.inline_shapes), 7)
            self.assertTrue(word_images_match_capture_digests(output, digests))
            text = "\n".join(p.text for p in word.paragraphs)
            self.assertNotIn("وفق سجل التسليم فقط", text)
            self.assertIn("نُشر خلال الساعة المكتملة السابقة: 7 تغطية", text)

    def test_hourly_recovery_cannot_be_misrepresented_as_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            daily, digests = MinistryMediaLayoutNoSend()._report(root, 2)
            labeled = [
                dict(daily["articles"][0],
                     hourly_publication_bucket="within_previous_hour"),
                dict(daily["articles"][1],
                     hourly_publication_bucket="recovered_older"),
            ]
            hourly = {**daily, "articles": labeled, "report_period": "interval",
                      "report_kind": "hourly", "hourly_in_period": 1,
                      "hourly_recovered": 1, "ministry_media_grid": True,
                      "coverage": "HEALTHY",
                      "sources": [{"feed_id": "hapi", "status": "ok",
                                   "verified_links": 2}]}
            result = root / "backlog-labeled.docx"
            render_docx(hourly, result)
            word = Document(result)
            self.assertEqual(len(word.inline_shapes), 2)
            self.assertTrue(word_images_match_capture_digests(result, digests))
            paragraph_text = "\n".join(p.text for p in word.paragraphs)
            self.assertIn("نُشر خلال الساعة المكتملة السابقة: 1 تغطية", paragraph_text)
            self.assertIn("استدراك أخبار منشورة قبلها: 1", paragraph_text)
            self.assertTrue(any("استدراك: نُشر قبل الساعة الحالية" in
                                cell.text for table in word.tables
                                for row in table.rows for cell in row.cells))
            hourly["hourly_in_period"] = 2
            hourly["hourly_recovered"] = 0
            with self.assertRaisesRegex(ValueError, "classification_hold"):
                render_docx(hourly, root / "incorrect-backlog.docx")

    def test_unknown_or_unverified_interval_cannot_claim_final_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample, _ = MinistryMediaLayoutNoSend()._report(root, 1)
            sample.update({"report_period": "interval", "coverage": "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS"})
            with self.assertRaisesRegex(ValueError, "rasd_visual_interval_status_untrusted"):
                render_docx(sample, root / "forbidden.docx")
            self.assertFalse((root / "forbidden.docx").exists())


if __name__ == "__main__":
    unittest.main()
