"""No-send adaptive layout: exact original images and strict archive compatibility."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from docx import Document
from docx.shared import Cm
from PIL import Image, ImageDraw
from daily_report import render_docx
from daily_sent_consolidator import extract_sent_originals
from monitor import article_id
from cloud_proof_report import word_images_match_capture_digests
import test_ministry_visual_daily_layout as fixtures

class AdaptiveLayout(unittest.TestCase):
    def test_all_remainders_and_archive_order(self):
        for count in (1,2,3,4,5,6,7,8,10,15):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as d:
                root=Path(d)
                report,proofs=fixtures.MinistryMediaLayoutNoSend()._report(root,count)
                report.update(report_period="interval",report_kind="half_hourly",
                    coverage="HEALTHY",sources=[{"feed_id":"hapi","status":"ok"}])
                # Unique synthetic publisher images even beyond the base fixture's
                # saturated color range. The production duplicate guard stays intact.
                for i,(a,proof) in enumerate(zip(report["articles"],proofs)):
                    image=Path(a["evidence_image_path"])
                    with Image.open(image) as original:
                        pic=original.copy()
                    ImageDraw.Draw(pic).rectangle((20+i*20,40,35+i*20,110),fill="white")
                    pic.save(image,"JPEG",quality=88)
                    proof["sha256"]=hashlib.sha256(image.read_bytes()).hexdigest()
                self.assertEqual(len({x["sha256"] for x in proofs}),count)
                target=root/"test.docx";render_docx(report,target);doc=Document(target)
                cards=[c for t in doc.tables[2:] for row in t.rows for c in row.cells]
                self.assertEqual(len(cards),count)
                self.assertEqual(len(doc.inline_shapes),count)
                self.assertTrue(word_images_match_capture_digests(target,proofs))
                for i,c in enumerate(cards):
                    self.assertTrue(c.paragraphs[0].text.startswith(f"{i+1:02d}  |  "))
                    self.assertEqual(c.paragraphs[1].text,report["articles"][i]["headline"])
                    self.assertEqual(len(c._tc.xpath(".//a:blip")),1)
                self.assertEqual(len(doc.element.xpath("//w:gridSpan")),0)
                expected=[{**a,"id":article_id(a["url"])} for a in report["articles"]]
                dest=root/"extracted";dest.mkdir()
                items=extract_sent_originals(target.read_bytes(),expected,dest)
                self.assertEqual([a["id"] for a,_,_ in items],[a["id"] for a in expected])
                self.assertEqual([h for _,_,h in items],[x["sha256"] for x in proofs])
    def test_larger_tail_images_without_crop(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r,proof=fixtures.MinistryMediaLayoutNoSend()._report(root,6)
            p=root/"daily.docx";render_docx(r,p);doc=Document(p)
            shapes=doc.inline_shapes
            self.assertEqual(len(shapes),6)
            self.assertGreater(shapes[4].width,shapes[0].width)
            self.assertGreater(shapes[5].width,shapes[0].width)
            for sh in shapes:
                self.assertAlmostEqual(sh.width/sh.height,1200/900,places=3)
                self.assertLessEqual(sh.width,Cm(16))
            self.assertTrue(word_images_match_capture_digests(p,proof))
    def test_summary_distinguishes_coverage_from_events(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r,_=fixtures.MinistryMediaLayoutNoSend()._report(root,3)
            p=root/"daily.docx";render_docx(r,p);doc=Document(p)
            self.assertIn("العدد للتغطيات لا للأحداث المستقلة", "\n".join(x.text for x in doc.paragraphs))
            self.assertEqual(doc.tables[1].cell(0,1).text,"التغطيات")
if __name__=="__main__":unittest.main()
