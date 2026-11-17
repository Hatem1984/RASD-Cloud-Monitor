"""Rendered Word QA: Arabic complex typography and one-clip readability.

Images here are SYNTHETIC fixture data only; not real publisher proof.
All original JPEG SHA acceptance gates are preserved.
"""
import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx
from test_ministry_visual_daily_layout import MinistryMediaLayoutNoSend


class MinistryWordReadabilityQA(unittest.TestCase):
    def test_complex_script_actual_cover_size_and_two_line_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            report,proofs=MinistryMediaLayoutNoSend()._report(folder,4)
            path=folder/"cover.docx"
            render_docx(report,path)
            doc=Document(path)
            cover=doc.tables[0].cell(0,0)
            title=[r for p in cover.paragraphs for r in p.runs
                   if r.text == "تقرير رصد"]
            self.assertEqual(len(title),1)
            props=title[0]._r.get_or_add_rPr()
            self.assertEqual(props.find(qn("w:szCs")).get(qn("w:val")),"52")
            self.assertEqual(props.find(qn("w:rFonts")).get(qn("w:cs")),
                             "DejaVu Sans")
            text=" ".join(p.text for p in cover.paragraphs)
            self.assertIn(report["display_window_start"],text)
            self.assertIn(report["display_window_end"],text)
            self.assertIn("التغطيات المصوّرة: 4",text)
            self.assertIn("المواقع الممثلة: 4",text)
            self.assertTrue(word_images_match_capture_digests(path,proofs))

    def test_only_one_clipping_uses_wide_original_jpeg_not_half_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            report,proofs=MinistryMediaLayoutNoSend()._report(folder,1)
            path=folder/"single.docx"
            render_docx(report,path)
            doc=Document(path)
            self.assertEqual(len(doc.inline_shapes),1)
            self.assertGreater(doc.inline_shapes[0].width.cm,12)
            self.assertEqual(len(doc.tables[-1].columns),1)
            self.assertTrue(word_images_match_capture_digests(path,proofs))

    def test_multiple_clippings_remain_two_column_with_matching_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            report,proofs=MinistryMediaLayoutNoSend()._report(folder,4)
            path=folder/"four.docx"
            render_docx(report,path)
            doc=Document(path)
            self.assertEqual(len(doc.inline_shapes),4)
            self.assertEqual(len(doc.tables[-1].columns),2)
            self.assertLess(doc.inline_shapes[0].width.cm,9)
            self.assertTrue(word_images_match_capture_digests(path,proofs))

    def test_single_news_summary_has_no_wrong_singular_site_inflection(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            report,_=MinistryMediaLayoutNoSend()._report(folder,1)
            path=folder/"single.docx"
            render_docx(report,path)
            text=" ".join(p.text for p in Document(path).paragraphs)
            self.assertIn("عدد المواقع الممثلة 1",text)
            self.assertNotIn("1 موقعًا",text)


if __name__=="__main__":
    unittest.main()
