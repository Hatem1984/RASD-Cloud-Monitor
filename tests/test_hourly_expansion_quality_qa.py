"""Requested 100-source scope: all assertions offline, zero network or SMTP."""
import json
import unittest
from pathlib import Path
from rasd_hourly_expansion_qa import (
    hourly_slots,hourly_schedule,deduplicate_publisher_stories,
    proposed_catalog_status)
ROOT=Path(__file__).resolve().parents[1]
def story(url,headline="وزارة التخطيط تتابع تنفيذ مشروع التنمية الإقليمية",
          publication="2026-11-05T12:10:00+02:00",kind="news"):
    return {"url":url,"headline":headline,"published_at_cairo":publication,
            "source":"Original publisher","content_kind":kind}
class HourlyExpansionQA(unittest.TestCase):
    def test_hourly_owner_window_22_not_44(self):
        self.assertEqual(len(hourly_slots()),22)
        self.assertEqual(hourly_slots()[0],"00:00")
        self.assertEqual(hourly_slots()[-1],"21:00")
        self.assertEqual(hourly_schedule(),"7 0-21 * * *")
    def test_same_original_link_utm_is_one(self):
        a=story("https://publisher.eg/news/one?utm_source=foo")
        b=story("https://publisher.eg/news/one?utm_source=bar")
        self.assertEqual(len(deduplicate_publisher_stories([a,b])[0]["originals"]),1)
    def test_syndicated_same_story_preserves_two_original_publishers(self):
        a=story("https://publisher-one.eg/news/a")
        b=story("https://publisher-two.eg/story/b")
        groups=deduplicate_publisher_stories([a,b])
        self.assertEqual(len(groups),1)
        self.assertEqual({x["publisher_host"] for x in groups[0]["originals"]},
                         {"publisher-one.eg","publisher-two.eg"})
        self.assertTrue(groups[0]["must_capture_original_each"])
    def test_conservative_normalization_arabic_punctuation(self):
        a=story("https://one.eg/a",headline="وزير التخطيط: يناقش برنامج التنمية الاقتصادية")
        b=story("https://two.eg/b",headline="وزير التخطيط يناقش برنامج التنمية الاقتصادية")
        self.assertEqual(len(deduplicate_publisher_stories([a,b])),1)
    def test_different_headline_is_not_silently_suppressed(self):
        a=story("https://one.eg/a")
        b=story("https://two.eg/b",
                headline="وزارة التخطيط تعلن مخصصات إضافية لمشروع التنمية")
        self.assertEqual(len(deduplicate_publisher_stories([a,b])),2)
    def test_different_day_is_not_same_event_automatically(self):
        a=story("https://one.eg/a")
        b=story("https://two.eg/b",publication="2026-11-06T08:00:00+02:00")
        self.assertEqual(len(deduplicate_publisher_stories([a,b])),2)
    def test_naive_publication_date_fails(self):
        with self.assertRaises(ValueError):
            deduplicate_publisher_stories([story("https://one.eg/a",publication="2026-11-05T12:10:00")])
    def test_news_reports_analyses_are_eligible_for_original_capture(self):
        a=story("https://one.eg/news",kind="news")
        b=story("https://one.eg/report",kind="report",headline="تقرير تفصيلي عن مشروعات التخطيط")
        c=story("https://one.eg/analysis",kind="analysis",headline="تحليل أثر الموازنة على تنمية الأقاليم")
        groups=deduplicate_publisher_stories([a,b,c])
        self.assertEqual(len(groups),3)
        self.assertTrue(all(r["must_capture_original_each"] for r in groups))
    def test_report_and_analysis_are_not_hidden_by_same_title_news(self):
        title="وزارة التخطيط تراجع أثر برنامج التنمية في المحافظات"
        a=story("https://one.eg/news",headline=title,kind="news")
        b=story("https://two.eg/report",headline=title,kind="report")
        c=story("https://three.eg/analysis",headline=title,kind="analysis")
        self.assertEqual(len(deduplicate_publisher_stories([a,b,c])),3)
    def test_similar_cross_publisher_titles_are_flagged_not_silently_deleted(self):
        from rasd_hourly_expansion_qa import require_crosspublisher_review_closed
        a=story("https://one.eg/news/a",
                headline="وزارة التخطيط تبحث مشروعات تنمية المحافظات وتطوير البنية الأساسية")
        b=story("https://two.eg/news/b",
                headline="وزارة التخطيط تبحث مشروعات تنمية المحافظات وتطوير البنية الأساسية الجديدة")
        clusters=deduplicate_publisher_stories([a,b])
        self.assertEqual(len(clusters),2)
        self.assertEqual(len(clusters[0]["possible_duplicate_story_keys"]),1)
        with self.assertRaisesRegex(ValueError,"possible_crosspublisher_duplicate_requires_review"):
            require_crosspublisher_review_closed(clusters)
    def test_unrelated_titles_do_not_flag_potential_duplicates(self):
        from rasd_hourly_expansion_qa import require_crosspublisher_review_closed
        a=story("https://one.eg/a")
        b=story("https://two.eg/b",
                headline="وزارة المالية تعلن تطورات إيرادات الضرائب على الدخل")
        self.assertTrue(require_crosspublisher_review_closed(
            deduplicate_publisher_stories([a,b])))
    def test_unapproved_content_type_rejected(self):
        with self.assertRaisesRegex(ValueError,"content_kind"):
            deduplicate_publisher_stories([story("https://one.eg/a",kind="social")])
    def test_conflicting_identity_must_hold(self):
        a=story("https://one.eg/a",headline="وزارة التخطيط تصدر تقرير الاقتصاد")
        b=story("https://one.eg/a",headline="وزارة التخطيط تصدر تقريرًا آخر عن الاستثمارات")
        with self.assertRaisesRegex(ValueError,"duplicate_original_conflicting_identity"):
            deduplicate_publisher_stories([a,b])
    def test_researched_50_does_not_mean_100_verified(self):
        sources=json.loads((ROOT/"research_sources_top50.json").read_text(encoding="utf-8"))["sources"]
        feeds=json.loads((ROOT/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))["feeds"]
        result=proposed_catalog_status(feeds,sources)
        self.assertEqual(result["requested_sources"],100)
        self.assertEqual(result["active_approved_native_rss"],13)
        self.assertEqual(result["already_researched_distinct_sources"],50)
        self.assertEqual(result["unresearched_to_target"],50)
        self.assertIn("HOLD_",result["activation_state"])
if __name__=="__main__":unittest.main()
