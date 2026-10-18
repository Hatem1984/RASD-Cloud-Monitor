"""Gate 37: native publisher RSS relevance and publication clock regressions.

No network, outside-provider content, mail, schedule or private data. Tests
must preserve ALL production Ministry of Planning search phrases unchanged.
"""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from gate11_runner import candidate_from_feed
from daily_report import gather
from monitor import inspect, parse_rss

CONFIG = json.loads(Path("sources.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 18, 8, 0, tzinfo=timezone.utc)


def rss(title, url, *, description="", published="Sun, 18 Oct 2026 07:00:00 GMT",
        dc_date=None):
    dc_tag = (f"<dc:date>{escape(dc_date)}</dc:date>" if dc_date else "")
    return (
        '<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item>'
        f"<title>{escape(title)}</title><link>{escape(url)}</link>"
        f"<description>{escape(description)}</description>"
        f"<pubDate>{escape(published)}</pubDate>{dc_tag}"
        "</item></channel></rss>"
    ).encode("utf-8")


class MinistryNativeDiscoveryTests(unittest.TestCase):
    def test_saved_production_ministry_keywords_are_exact_and_unchanged(self):
        self.assertEqual(CONFIG["keywords"], [
            "وزارة التخطيط", "وزير التخطيط",
            "وزيرة التخطيط", "التخطيط والتنمية الاقتصادية",
        ])
        self.assertEqual(CONFIG["scope"], "Egyptian Ministry of Planning - publicly published news only")
        self.assertEqual([f["id"] for f in CONFIG["feeds"]], ["hapi", "almasryalyoum"])

    def test_each_saved_term_matches_in_publisher_description_for_both_sources(self):
        for feed in CONFIG["feeds"]:
            for keyword in CONFIG["keywords"]:
                with self.subTest(feed=feed["id"], keyword=keyword):
                    link = ("https://hapijournal.com/news/test-original"
                            if feed["id"] == "hapi" else
                            "https://www.almasryalyoum.com/news/details/1234567")
                    content = rss(
                        "خبر اقتصادي يذكر مؤشرات التنمية",
                        link, description=f"<p>بحسب الناشر: {keyword} تعقد اجتماعا</p>")
                    links, matched = parse_rss(content, feed, CONFIG["keywords"], now=NOW)
                    self.assertEqual(links, 1)
                    self.assertEqual(len(matched), 1)
                    self.assertEqual(matched[0]["match_origin"], "publisher_description")
                    self.assertIn(keyword, matched[0]["publisher_excerpt"])
                    self.assertIsNotNone(candidate_from_feed(matched[0], CONFIG, NOW))

    def test_arabic_diacritics_and_tatweel_do_not_hide_saved_ministry_term(self):
        feed = CONFIG["feeds"][0]
        xml = rss(
            "تقرير عن وَزَارَةُ الـتَّخطيطِ والتَّنمية",
            "https://hapijournal.com/article/arabic-typography")
        _, found = parse_rss(xml, feed, CONFIG["keywords"], now=NOW)
        self.assertEqual(len(found), 1)

    def test_unrelated_generic_economic_news_is_not_selected(self):
        for feed in CONFIG["feeds"]:
            link = ("https://hapijournal.com/economy-generic"
                    if feed["id"] == "hapi" else
                    "https://www.almasryalyoum.com/news/details/1234567")
            payload = rss("نمو الاقتصاد المصري", link,
                          description="البورصة والقطاع الخاص وخطط التنمية")
            _, found = parse_rss(payload, feed, CONFIG["keywords"], now=NOW)
            self.assertEqual(found, [])

    def test_title_match_is_not_lost_and_retains_priority(self):
        feed = CONFIG["feeds"][0]
        payload = rss(
            "وزارة التخطيط تعقد مؤتمرًا",
            "https://hapijournal.com/news/title-match",
            description="سوق المال والتداول")
        _, found = parse_rss(payload, feed, CONFIG["keywords"], now=NOW)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["match_origin"], "title")

    def test_dublin_core_iso_date_with_explicit_offset_becomes_aware_rfc2822(self):
        feed = CONFIG["feeds"][0]
        payload = rss(
            "وزير التخطيط",
            "https://hapijournal.com/news/dated-iso",
            published="", dc_date="2026-10-18T09:00:00+03:00")
        _, found = parse_rss(payload, feed, CONFIG["keywords"], now=NOW)
        self.assertEqual(len(found), 1)
        self.assertEqual(
            parsedate_to_datetime(found[0]["published"]).astimezone(timezone.utc),
            datetime(2026, 10, 18, 6, 0, tzinfo=timezone.utc))
        self.assertIsNotNone(candidate_from_feed(found[0], CONFIG, NOW))

    def test_missing_and_naive_iso_publisher_dates_not_guessed(self):
        feed = CONFIG["feeds"][0]
        for date in (None, "2026-10-18T07:00:00", "bad-date"):
            with self.subTest(dc_date=date):
                payload = rss(
                    "وزارة التخطيط تنشر قرارًا",
                    "https://hapijournal.com/news/undated",
                    published="", dc_date=date)
                _, found = parse_rss(payload, feed, CONFIG["keywords"], now=NOW)
                self.assertEqual(found, [])

    def test_stale_or_future_iso_dates_are_not_reinterpreted_as_today(self):
        feed = CONFIG["feeds"][0]
        for d in ("2024-10-18T07:00:00Z", "2026-10-19T10:00:00+03:00"):
            with self.subTest(date=d):
                xml = rss("وزارة التخطيط", "https://hapijournal.com/news/dating",
                          published="", dc_date=d)
                _, found = parse_rss(xml, feed, CONFIG["keywords"], now=NOW)
                self.assertEqual(found, [])

    def test_reject_third_party_urls_even_with_matching_publisher_description(self):
        feed = CONFIG["feeds"][1]
        xml = rss("موضوع", "https://news.google.com/rss/articles/fake",
                  description="وزارة التخطيط")
        n, matches = parse_rss(xml, feed, CONFIG["keywords"], now=NOW)
        self.assertEqual((n, matches), (0, []))

    def test_cairo_midnight_falls_on_correct_publisher_calendar_day(self):
        feed = CONFIG["feeds"][0]
        cairo = ZoneInfo("Africa/Cairo")
        current = datetime(2026, 10, 18, 10, 0, tzinfo=cairo)
        xml = rss("لقاء اقتصادي دوري",
                  "https://hapijournal.com/news/planning-before-midnight",
                  description="وزير التخطيط عقد مباحثات",
                  published="", dc_date="2026-10-17T23:58:00+03:00")
        def fetch(url, size):
            return xml if url == feed["url"] else (
                b"<rss><channel></channel></rss>")
        report = gather(CONFIG, fetch=fetch, now=current)
        self.assertEqual(len(report["articles"]), 1)
        self.assertTrue(report["articles"][0]["published_at_cairo"].startswith(
            "2026-10-17 23:58"))
        self.assertEqual(report["articles"][0]["publisher_excerpt"],
                         "وزير التخطيط عقد مباحثات")
        scan = inspect(CONFIG, fetch=fetch, now=current)
        self.assertEqual(scan["native_description_matches"], 1)
        self.assertEqual(scan["sources"][0]["description_matches"], 1)
        self.assertFalse(scan["rss_feed_is_exhaustive_archive"])
        self.assertFalse(scan["email_sent"])
        self.assertFalse(scan["scheduler_enabled"])

    def test_unsafe_pubdate_does_not_fall_back_to_dc_date_inconsistent(self):
        feed = CONFIG["feeds"][0]
        xml = rss("وزارة التخطيط", "https://hapijournal.com/news/bad-clock",
                  published="not-a-valid-date", dc_date="2026-10-18T07:00:00Z")
        _, found = parse_rss(xml, feed, CONFIG["keywords"], now=NOW)
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
