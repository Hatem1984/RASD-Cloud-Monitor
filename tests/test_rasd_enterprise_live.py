"""Offline private live-source guards; never sends mail or reads production CAS."""
from __future__ import annotations
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch

from rasd_app.enterprise import EnterpriseStore, _same_event, _window
from rasd_app.core import utcnow

HAPI="https://hapijournal.com/feed/"
SHOROUK="https://www.shorouknews.com/Economy/rss"


def story(title,url,publisher,days=0):
    return {"title":title,"url":url,"publisher":publisher,
            "published":(datetime.now(timezone.utc)+timedelta(days=days,minutes=-2)).isoformat()}


class EnterpriseLiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=EnterpriseStore(self.tmp.name,live_only=True)
        self.tid=self.store.create_tenant(
            "رصد اقتصاد حقيقي",topics=["الاقتصاد"],
            includes=["الاقتصاد","التمويل","المالية"],
            excludes=["كرة القدم"],target=10,duplicate_policy="coverages")
        self.store.add_source(self.tid,"حابي",HAPI)
        self.store.add_source(self.tid,"الشروق",SHOROUK)

    def test_live_source_failure_preserves_other_and_no_demo_fallback(self):
        feed=[
            story("وزير المالية يعلن تعديل برنامج التمويل","https://hapijournal.com/live/test-1","hapijournal.com"),
            story("كرة القدم والمالية في إعلان النادي","https://hapijournal.com/live/test-2","hapijournal.com"),
            story("عاجل خبر آخر عن التمويل","https://hapijournal.com/live/test-3","hapijournal.com",days=-5),
            story("النشاط الرياضي","https://hapijournal.com/live/test-4","hapijournal.com"),
        ]
        def load(url):
            if url==HAPI:return feed
            raise RuntimeError("feed_http_or_redirect_error")
        sid,created=self.store.start_scan(self.tid)
        with patch("rasd_app.enterprise.parse_live_feed",side_effect=load),patch(
             "rasd_app.enterprise.demo_items",side_effect=AssertionError("demo invoked")):
            self.store.run_scan(self.tid,sid)
        scan=self.store.list_scans(self.tid)[0]
        self.assertEqual(scan["status"],"partial")
        summary=json.loads(scan["summary"])
        self.assertEqual(summary["sources_ok"],1)
        self.assertEqual(summary["sources_unavailable"],1)
        self.assertEqual(summary["new_matching_coverages"],1)
        self.assertEqual(summary["outside_window"],1)
        self.assertEqual(summary["excluded_or_unmatched"],2)
        checks=self.store.source_checks(self.tid,sid)
        self.assertEqual(len(checks),2)
        good=next(x for x in checks if x["status"]=="ok")
        bad=next(x for x in checks if x["status"]=="unavailable")
        self.assertEqual((good["scanned"],good["matched"],good["excluded"],good["outside_window"]),(4,1,2,1))
        self.assertEqual(bad["reason"],"feed_http_or_redirect_error")
        self.assertTrue(good["checked_at"])
        self.assertEqual(len(self.store.articles(self.tid)),1)
        self.assertFalse(self.store.articles(self.tid)[0]["demo"])

    def test_zero_window_has_zero_with_explanation(self):
        sid,_=self.store.start_scan(
            self.tid,(datetime.now(timezone.utc)-timedelta(days=2)).isoformat(),
            (datetime.now(timezone.utc)-timedelta(days=1)).isoformat())
        with patch("rasd_app.enterprise.parse_live_feed",return_value=[
                 story("أخبار التمويل اليوم","https://hapijournal.com/live/today","hapijournal.com")]):
            self.store.run_scan(self.tid,sid)
        s=self.store.list_scans(self.tid)[0]
        result=json.loads(s["summary"])
        self.assertEqual(s["status"],"complete")
        self.assertEqual(result["new_matching_coverages"],0)
        self.assertGreater(result["outside_window"],0)
        self.assertEqual(len(self.store.articles(self.tid)),0)

    def test_strict_timewindow(self):
        for a,b in ((None,"2026-11-23T01:00:00+00:00"),("2026-11-23","2026-11-24"),
                   ("2026-11-25T10:00:00Z","2026-11-24T11:00:00Z"),
                   ("2025-01-01T00:00:00Z","2026-11-23T01:00:00Z")):
            with self.subTest(a=a,b=b),self.assertRaises(ValueError):
                _window(a,b)

    def test_no_demo_mixed_with_real_even_when_requested(self):
        with self.assertRaisesRegex(ValueError,"demo_source_forbidden"):
            self.store.add_source(self.tid,"fake","demo://foods")
        with tempfile.TemporaryDirectory() as tmp:
            normal=EnterpriseStore(tmp)
            t=normal.create_tenant("عرض توضيحي")
            normal.add_source(t,"fixture","demo://university")
            with self.assertRaisesRegex(ValueError,"cannot_mix_demo"):
                normal.add_source(t,"real",HAPI)
            self.assertEqual(normal.tenant(t)["mode"],"demo")

    def test_original_capture_failure_recorded_and_review_reason(self):
        sid,_=self.store.start_scan(self.tid)
        with patch("rasd_app.enterprise.parse_live_feed",return_value=[
                 story("وزير المالية يناقش التمويل","https://hapijournal.com/live/review","hapijournal.com")]):
            self.store.run_scan(self.tid,sid)
        article=self.store.articles(self.tid)[0]
        with patch("rasd_app.capture.capture_manual_article",
                   return_value={"ok":False,"reason":"publisher_access_refused"}):
            outcome=self.store.capture_original(self.tid,article["id"])
        self.assertFalse(outcome["ok"])
        row=self.store.article(self.tid,article["id"])
        self.assertEqual(row["image_error"],"publisher_access_refused")
        self.assertEqual(row["image_state"],"missing")
        with self.assertRaisesRegex(ValueError,"rejection_reason_required"):
            self.store.review(self.tid,article["id"],"reviewer","rejected")
        self.store.review(self.tid,article["id"],"reviewer","rejected",reason="صورة الناشر لم تظهر")
        self.assertEqual(json.loads(self.store.article(self.tid,article["id"])["review_log"])[-1]["reason"],
                         "صورة الناشر لم تظهر")

    def test_three_coverage_one_event_but_two_different_finance_figures(self):
        titles=[
            "وزير المالية يعلن إطلاق برنامج دعم الصادرات بقيمة 500 مليون جنيه",
            "إطلاق برنامج دعم الصادرات بقيمة ٥٠٠ مليون جنيه أعلن عنه وزير المالية",
            "برنامج دعم الصادرات بقيمة 500 مليون جنيه يعلنه وزير المالية",
            "وزير المالية يعلن إطلاق برنامج دعم الصادرات بقيمة 600 مليون جنيه"]
        self.assertTrue(_same_event(titles[0],titles[1]))
        self.assertTrue(_same_event(titles[0],titles[2]))
        self.assertFalse(_same_event(titles[0],titles[3]))
        sid,_=self.store.start_scan(self.tid)
        rows=[story(t,"https://hapijournal.com/live/event-"+str(i),"hapijournal.com")
              for i,t in enumerate(titles)]
        with patch("rasd_app.enterprise.parse_live_feed",return_value=rows):
            self.store.run_scan(self.tid,sid)
        # These specific titles do not match pre-set finance terms. Set
        # tenant-specific reviewed terms before actual scan in this test.
        self.assertEqual(len(self.store.articles(self.tid)),4)
        grouped=[r["event_key"] for r in self.store.articles(self.tid)]
        self.assertEqual(len(set(grouped)),2)

if __name__=="__main__":
    unittest.main()
