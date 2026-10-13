"""Gate 11: original-publisher feed expansion, offline only.

All network interactions are simulated. No Gmail, GitHub private writes,
credentials, paid services or real network traffic are used in these tests.
"""
from __future__ import annotations

import os
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from capture_public import allowed_url
from gate11_runner import candidate_from_feed, run
from monitor import (APPROVED_FEED_URLS, article_id, inspect,
                     parse_rss, read_feed)

CURRENT = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
CONFIG = json.loads(Path("sources.json").read_text(encoding="utf-8"))
HAPI_URL = "https://hapijournal.com/news-planning-example"
MASRY_URL = "https://www.almasryalyoum.com/news/details/4380924"
HEADLINE = "وزارة التخطيط تستعرض مؤشرات التنمية في مصر"
PUBLISHED = "Tue, 13 Oct 2026 09:00:00 +0300"


def feed_xml(url: str, *, title=HEADLINE, published=PUBLISHED) -> bytes:
    return (f"<rss><channel><item><title>{title}</title>"
            f"<link>{url}</link><pubDate>{published}</pubDate>"
            f"</item></channel></rss>").encode("utf-8")


class OriginalPublisherExpansionTests(unittest.TestCase):
    def test_exactly_two_reviewed_native_feed_endpoints(self):
        self.assertEqual(set(APPROVED_FEED_URLS), {
            "https://hapijournal.com/feed/",
            "https://www.almasryalyoum.com/rss/rssfeeds",
        })
        self.assertEqual({f["url"] for f in CONFIG["feeds"]},
                         set(APPROVED_FEED_URLS))

    def test_reject_similar_looking_or_unreviewed_feed_urls_before_network(self):
        for url in (
            "https://www.almasryalyoum.com/rss/rssfeeds?unreviewed=1",
            "https://www.almasryalyoum.com/other/path",
            "https://www.almasryalyoum.com.evil.example/rss/rssfeeds",
            "http://www.almasryalyoum.com/rss/rssfeeds",
            "https://127.0.0.1/rss/rssfeeds",
            "https://hapijournal.com/somewhere-else",
        ):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ValueError, "feed_endpoint_not_reviewed"):
                    read_feed(url, 100_000)

    def test_second_publisher_owned_article_candidate_with_native_date(self):
        feed = next(x for x in CONFIG["feeds"] if x["id"] == "almasryalyoum")
        self.assertTrue(allowed_url(MASRY_URL, "almasryalyoum.com"))
        count, matches = parse_rss(feed_xml(MASRY_URL), feed,
                                   CONFIG["keywords"], now=CURRENT)
        self.assertEqual((count, len(matches)), (1, 1))
        candidate = candidate_from_feed(matches[0], CONFIG, CURRENT)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["url"], MASRY_URL)
        self.assertEqual(candidate["id"], article_id(MASRY_URL))
        self.assertEqual(candidate["publisher"], "almasryalyoum.com")

    def test_cross_publisher_or_aggregator_urls_are_rejected(self):
        feed = next(x for x in CONFIG["feeds"] if x["id"] == "almasryalyoum")
        for url in (HAPI_URL, "https://news.google.com/rss/articles/x",
                    "https://almasryalyoum.com.evil.example/news/details/1"):
            with self.subTest(url=url):
                count, matches = parse_rss(feed_xml(url), feed,
                                           CONFIG["keywords"], now=CURRENT)
                self.assertEqual((count, matches), (0, []))

    def test_both_sources_and_partial_failure_are_handled_independently(self):
        hapi = next(f for f in CONFIG["feeds"] if f["id"] == "hapi")
        masry = next(f for f in CONFIG["feeds"] if f["id"] == "almasryalyoum")
        def fetch(url, limit):
            if url == hapi["url"]:
                raise TimeoutError("simulated publisher outage")
            if url == masry["url"]:
                return feed_xml(MASRY_URL)
            raise AssertionError("unreviewed feed")
        result = inspect(CONFIG, fetch=fetch, now=CURRENT)
        self.assertEqual([s["status"] for s in result["sources"]],
                         ["failed", "ok"])
        self.assertEqual(result["planning_headline_matches"], 1)
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["email_sent"])

    def test_partial_live_source_outage_is_visible_not_false_full_success(self):
        hapi = next(f for f in CONFIG["feeds"] if f["id"] == "hapi")
        masry = next(f for f in CONFIG["feeds"] if f["id"] == "almasryalyoum")
        def simulated_fetch(url, limit):
            if url == hapi["url"]:
                raise TimeoutError("controlled outage")
            if url == masry["url"]:
                return feed_xml(MASRY_URL, title="خبر رياضي لا يخص الوزارة")
            raise AssertionError("unexpected URL")
        with patch.dict(os.environ, {}, clear=True):
            result = run("dry_run", fetch=simulated_fetch, clock=CURRENT)
        self.assertEqual(result["healthy_sources"], 1)
        self.assertEqual(result["failed_sources"], 1)
        self.assertEqual(result["coverage_status"], "degraded")
        self.assertEqual(result["smtp_accepted"], 0)
        self.assertEqual(result["source_health"], [
            {"feed_id": "hapi", "status": "failed", "error_type": "TimeoutError"},
            {"feed_id": "almasryalyoum", "status": "ok", "error_type": None},
        ])
        self.assertFalse(result["scheduler_enabled"])

    def test_transient_bad_rss_recovers_on_one_retry(self):
        calls = {"masry": 0}
        def fetch_once_bad(url, limit):
            if "almasryalyoum" not in url:
                return feed_xml(HAPI_URL)
            calls["masry"] += 1
            return b"not valid xml" if calls["masry"] == 1 else feed_xml(MASRY_URL)
        result = inspect(CONFIG, fetch=fetch_once_bad, now=CURRENT)
        self.assertEqual(calls["masry"], 2)
        self.assertEqual([s["status"] for s in result["sources"]], ["ok", "ok"])
        self.assertEqual(result["planning_headline_matches"], 2)

    def test_transient_timeout_recovers_without_double_count(self):
        calls = {"masry": 0}
        def fetch_once_slow(url, limit):
            if "almasryalyoum" not in url:
                return feed_xml(HAPI_URL)
            calls["masry"] += 1
            if calls["masry"] == 1:
                raise TimeoutError("transient")
            return feed_xml(MASRY_URL)
        result = inspect(CONFIG, fetch=fetch_once_slow, now=CURRENT)
        self.assertEqual(calls["masry"], 2)
        self.assertEqual(result["planning_headline_matches"], 2)

    def test_no_automatic_capture_of_expired_native_publisher_story(self):
        feed = next(f for f in CONFIG["feeds"] if f["id"] == "almasryalyoum")
        _, matches = parse_rss(
            feed_xml(MASRY_URL, published="Sun, 01 Jan 2023 09:00:00 +0300"),
            feed, CONFIG["keywords"], now=CURRENT)
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
