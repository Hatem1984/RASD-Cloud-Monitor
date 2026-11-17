"""Report truthfulness: distinguish 100 research origins and 13 real feeds."""
import tempfile
import unittest
from pathlib import Path
from docx import Document
from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx
from test_ministry_visual_daily_layout import MinistryMediaLayoutNoSend


class MinistryScopeVisibilityNoSend(unittest.TestCase):
    def test_100_research_sources_are_not_displayed_as_100_live_publishers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            report,proof=MinistryMediaLayoutNoSend()._report(p,2)
            report["scope_note"]=(
                "13 مصدرًا نشطًا من قنوات RSS ضمن سجل بحث يضم 100 "
                "مصدر؛ 87 مرجعًا لم يعتمد للرصد الآلي.")
            path=p/"daily.docx"
            render_docx(report,path)
            d=Document(path)
            text=" ".join(x.text for x in d.paragraphs)
            self.assertIn("نطاق المصادر الفعلي",text)
            self.assertIn("13 مصدرًا نشطًا",text)
            self.assertIn("100 مصدر",text)
            self.assertIn("87 مرجعًا",text)
            self.assertEqual(len(d.inline_shapes),2)
            self.assertTrue(word_images_match_capture_digests(path,proof))

    def test_untrusted_scope_is_not_displayed_as_credible_research(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            report,_=MinistryMediaLayoutNoSend()._report(folder,1)
            for invalid in ({"bad":"input"}, "X"*1201):
                with self.subTest(invalid=str(invalid)[:12]):
                    report["scope_note"]=invalid
                    path=folder/"must-not-ship.docx"
                    with self.assertRaisesRegex(ValueError,
                                                 "source_scope_untrusted"):
                        render_docx(report,path)
                    self.assertFalse(path.exists())


if __name__=="__main__":
    unittest.main()
