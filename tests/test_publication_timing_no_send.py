"""No-send presentation tests. No network, ledger or SMTP calls."""
import copy
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from docx import Document
from daily_report import cairo_display_time, render_docx
from rasd_ministry_visual_layout import _publication_timing
from cloud_proof_report import word_images_match_capture_digests
import test_ministry_visual_daily_layout as fixtures

CAIRO=ZoneInfo("Africa/Cairo")
def label(y,m,d,h,mi):
    return cairo_display_time(datetime(y,m,d,h,mi,tzinfo=CAIRO))
def report(stamps,start=None,end=None):
    return {"display_window_start":start or label(2026,11,26,1,0),
            "display_window_end":end or label(2026,11,26,1,18),
            "articles":[{"published_at_cairo":v} for v in stamps]}
class PublicationTiming(unittest.TestCase):
    def test_minutes_and_dates(self):
        r=report(["2026-11-24 11:32 EET","2026-11-25 23:59 EET","2026-11-26 00:59 EET","2026-11-26 01:00 EET","2026-11-26 01:18 EET","2026-11-26 01:19 EET"])
        self.assertEqual(_publication_timing(r),["older","older","older","within","within","unknown"])
    def test_missing_invalid_and_wrong_zone(self):
        r=report([None,"2026-02-30 01:00 EET","2026-11-26 01:00 EEST","2026-11-26","fake"])
        self.assertEqual(_publication_timing(r),["unknown"]*5)
    def test_invalid_or_reversed_window(self):
        self.assertEqual(_publication_timing(report(["2026-11-26 01:00 EET"],start="not verified")),["unknown"])
        self.assertEqual(_publication_timing(report(["2026-11-26 01:00 EET"],start=label(2026,11,26,2,0))),["unknown"])
    def test_summer_time(self):
        r=report(["2026-07-09 22:59 EEST","2026-07-09 23:00 EEST","2026-07-09 23:00 EET"],start=label(2026,7,9,23,0),end=label(2026,7,9,23,30))
        self.assertEqual(_publication_timing(r),["older","within","unknown"])
    def test_ambiguous_clock_not_classified(self):
        # Cairo clocks roll from midnight back to 23:00 in late October.
        r=report(["2026-10-29 22:30 EEST"],start=label(2026,10,29,23,0),end=label(2026,10,30,0,30))
        self.assertEqual(_publication_timing(r),["unknown"])
    def test_document_preserves_items_and_original_digests(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r,receipts=fixtures.MinistryMediaLayoutNoSend()._report(root,3)
            r.update(report_period="interval",report_kind="half_hourly",coverage="HEALTHY",sources=[{"feed_id":"hapi","status":"ok"}],display_window_start=label(2026,11,26,1,0),display_window_end=label(2026,11,26,1,18))
            for item,t in zip(r["articles"],["2026-11-24 11:32 EET","2026-11-26 01:18 EET",None]):
                item["published_at_cairo"]=t;item["published_display_cairo"]="تاريخ عينة"
            original=copy.deepcopy(r);target=root/"timing.docx";render_docx(r,target);self.assertEqual(r,original)
            word=Document(target)
            self.assertEqual(len(word.inline_shapes),3)
            self.assertTrue(word_images_match_capture_digests(target,receipts))
            self.assertEqual({x.target_ref for x in word.part.rels.values() if x.reltype.endswith("/hyperlink")},{a["url"] for a in r["articles"]})
            self.assertIn("نافذة الفحص:",word.tables[0].cell(0,0).text)
            text="\n".join(p.text for p in word.paragraphs)
            self.assertIn("النشر ضمن نافذة الفحص: 1؛ استدراك قبل النافذة: 1؛ التوقيت غير محسوم: 1",text)
            cells="\n".join(c.text for t in word.tables for row in t.rows for c in row.cells)
            for s in ("النشر:","استدراك قبل نافذة الفحص","نُشر ضمن نافذة الفحص","توقيت النشر بالنسبة للنافذة غير محسوم"):
                self.assertIn(s,cells)
    def test_daily_delivery_window_is_not_publication_claim(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r,proof=fixtures.MinistryMediaLayoutNoSend()._report(root,1);p=root/"daily.docx";render_docx(r,p)
            doc=Document(p);self.assertIn("فترة التسليم:",doc.tables[0].cell(0,0).text)
            self.assertNotIn("استدراك قبل النافذة:", "\n".join(p.text for p in doc.paragraphs))
            self.assertTrue(word_images_match_capture_digests(p,proof))
if __name__=="__main__":unittest.main()
