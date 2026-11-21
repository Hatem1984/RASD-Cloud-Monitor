"""Strict fresh-hour 10 stories / 10 publishers: offline, no SMTP."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from monitor import article_id
from rasd_strict_hourly_ten_source_gate import (
    audit_fresh_distinct_sources, last_completed_hour,
    originals_report_ready,
)

NOW=datetime(2026,11,21,18,7,tzinfo=timezone.utc)
START,END=last_completed_hour(NOW)


def fixture(n=10, *, stamp=None):
    feeds=[{"name":f"Original Publisher {i}",
            "allowed_article_hosts":[f"news{i}.example.org"]} for i in range(n)]
    articles=[]
    for i in range(n):
        url=f"https://news{i}.example.org/planning/{i+1}/"
        published=stamp if stamp is not None else END-timedelta(minutes=15+i)
        articles.append({
            "id":article_id(url),"url":url,
            "headline":f"وزارة التخطيط تعلن مشروع التنمية المحلي رقم {i+11}",
            "source":feeds[i]["name"],
            "published":format_datetime(published),
        })
    return feeds,articles


class TenFreshDifferentNewsrooms(unittest.TestCase):
    def test_ten_publishers_ten_latest_hour_stories_pass_preflight(self):
        feeds,items=fixture()
        result=audit_fresh_distinct_sources(items,feeds,NOW)
        self.assertEqual(result["status"],"CANDIDATES_NEED_ORIGINAL_IMAGES")
        self.assertEqual(result["fresh_distinct_candidates"],10)
        self.assertEqual(result["different_sources"],10)
        self.assertEqual(len(result["selected"]),10)
        self.assertFalse(result["original_images_verified"])
        self.assertFalse(result["smtp_sent"])

    def test_only_nine_real_publishers_is_hold_no_partial_report(self):
        feeds,items=fixture(9)
        result=audit_fresh_distinct_sources(items,feeds,NOW)
        self.assertEqual(result["fresh_distinct_candidates"],9)
        self.assertEqual(result["status"],"HOLD_NOT_ENOUGH_FRESH_INDEPENDENT_SOURCES")
        self.assertEqual(result["selected"],[])

    def test_old_news_must_not_be_imported_to_fill_ten(self):
        feeds,items=fixture()
        items[9]["published"]=format_datetime(START-timedelta(seconds=1))
        result=audit_fresh_distinct_sources(items,feeds,NOW)
        self.assertEqual(result["fresh_distinct_candidates"],9)
        self.assertEqual(result["rejection_counts"]["not_in_last_completed_hour"],1)
        self.assertEqual(result["selected"],[])

    def test_unzoned_publisher_time_is_not_a_fresh_news_proof(self):
        feeds,items=fixture()
        items[2]["published"]="Sat, 21 Nov 2026 17:05:00"
        result=audit_fresh_distinct_sources(items,feeds,NOW)
        self.assertEqual(result["rejection_counts"]["wrong_original_date"],1)
        self.assertEqual(result["status"],"HOLD_NOT_ENOUGH_FRESH_INDEPENDENT_SOURCES")

    def test_ten_articles_from_one_publisher_cannot_fill_ten_sources(self):
        feeds,items=fixture()
        for i,item in enumerate(items[1:],1):
            item["source"]=feeds[0]["name"]
            item["url"]=f"https://news0.example.org/planning/{i+1}"
            item["id"]=article_id(item["url"])
        result=audit_fresh_distinct_sources(items,feeds,NOW)
        self.assertEqual(result["different_sources"],1)
        self.assertEqual(result["status"],"HOLD_NOT_ENOUGH_FRESH_INDEPENDENT_SOURCES")

    def test_ten_syndications_same_event_are_not_ten_different_stories(self):
        feeds,items=fixture()
        for item in items:
            item["headline"]="وزارة التخطيط تطلق مشروعات التنمية المحلية بقيمة 13 مليار جنيه"
            item["published"]=format_datetime(END-timedelta(minutes=12))
        result=audit_fresh_distinct_sources(items,feeds,NOW)
        self.assertLess(result["fresh_distinct_candidates"],10)
        self.assertGreater(result["rejection_counts"]["repeated_event"],0)

    def test_early_future_or_updated_timestamp_does_not_count(self):
        feeds,items=fixture()
        items[0]["published"]=format_datetime(END+timedelta(minutes=1))
        items[0]["updated_at"]=format_datetime(END-timedelta(minutes=5))
        result=audit_fresh_distinct_sources(items,feeds,NOW)
        self.assertEqual(result["fresh_distinct_candidates"],9)
        self.assertEqual(result["selected"],[])

    def test_wrong_host_or_recycled_id_cannot_forge_a_publisher(self):
        feeds,items=fixture()
        items[3]["url"]="https://news3.example.org.evil.invalid/planning/4"
        items[3]["id"]=article_id(items[3]["url"])
        result=audit_fresh_distinct_sources(items,feeds,NOW)
        self.assertEqual(result["rejection_counts"]["unverified_source"],1)
        self.assertEqual(result["selected"],[])

    def test_one_missing_original_screenshot_fails_final_ten(self):
        feeds,items=fixture()
        a=audit_fresh_distinct_sources(items,feeds,NOW)
        delivered=[{**i,"evidence_image_path":"already-verified-by-upstream.jpg"}
                   for i in a["selected"]]
        self.assertTrue(originals_report_ready(a,delivered))
        self.assertFalse(originals_report_ready(a,delivered[:9]))
        delivered[0]["evidence_image_path"]=""
        self.assertFalse(originals_report_ready(a,delivered))

    def test_hour_boundary_exact_start_inclusive_end_exclusive(self):
        feeds,items=fixture()
        items[0]["published"]=format_datetime(START)
        self.assertEqual(audit_fresh_distinct_sources(
            items,feeds,NOW)["fresh_distinct_candidates"],10)
        items[0]["published"]=format_datetime(END)
        self.assertEqual(audit_fresh_distinct_sources(
            items,feeds,NOW)["fresh_distinct_candidates"],9)

    def test_clock_daylight_offset_is_utc_stable(self):
        self.assertEqual(last_completed_hour(
            datetime(2026,7,21,20,5,tzinfo=timezone(timedelta(hours=3)))),
            (datetime(2026,7,21,16,0,tzinfo=timezone.utc),
             datetime(2026,7,21,17,0,tzinfo=timezone.utc)))

if __name__=="__main__":
    unittest.main()
