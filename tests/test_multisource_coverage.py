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
from gate11_runner import candidate_from_feed, eligible_candidates, run
from monitor import (APPROVED_FEED_URLS, article_id, inspect,
                     parse_rss, read_feed)

CURRENT = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
ALL_CONFIG = json.loads(Path("sources.json").read_text(encoding="utf-8"))
# Existing two-source regression fixtures retain their original scope.
CONFIG = {**ALL_CONFIG, "feeds": [f for f in ALL_CONFIG["feeds"] if f["id"] != "shorouk"]}
HAPI_URL = "https://hapijournal.com/news-planning-example"
MASRY_URL = "https://www.almasryalyoum.com/news/details/4380924"
HEADLINE = "وزارة التخطيط تستعرض مؤشرات التنمية في مصر"
PUBLISHED = "Tue, 13 Oct 2026 09:00:00 +0300"


def feed_xml(url: str, *, title=HEADLINE, published=PUBLISHED) -> bytes:
    return (f"<rss><channel><item><title>{title}</title>"
            f"<link>{url}</link><pubDate>{published}</pubDate>"
            f"</item></channel></rss>").encode("utf-8")


class OriginalPublisherExpansionTests(unittest.TestCase):
    def test_fourteen_reviewed_native_feed_endpoints(self):
        self.assertEqual(set(APPROVED_FEED_URLS), {
            "https://hapijournal.com/feed/",
            "https://almessa.gomhuriaonline.com/feed/",
            "https://www.elbalad.news/rss.aspx",
            "https://www.vetogate.com/rss.aspx",
            "https://www.dailynewsegypt.com/feed/",
            "https://www.egyptindependent.com/feed/",
            "https://egyptianstreets.com/feed/",
            "https://www.skynewsarabia.com/rss.xml",
            "https://inp.edu.eg/feed/",
            "https://www.almasryalyoum.com/rss/rssfeeds",
            "https://www.masrawy.com/rss/feed/35/%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1%20%D9%85%D8%B5%D8%B1-%D8%B3%D9%8A%D8%A7%D8%B3%D8%A9",
            "https://www.shorouknews.com/Economy/rss",
            "https://www.alborsaanews.com/category/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%89/feed",
        })
        self.assertEqual({f["url"] for f in ALL_CONFIG["feeds"]},
                         {"https://hapijournal.com/feed/",
                          "https://www.almasryalyoum.com/rss/rssfeeds"})
        opt_in = json.loads(Path("sources_shorouk.json").read_text())
        self.assertEqual([f["id"] for f in opt_in["feeds"]], ["shorouk"])
        self.assertIn(opt_in["feeds"][0]["url"], APPROVED_FEED_URLS)

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

    def test_rss_rate_limit_429_is_not_retried_or_falsely_healthy(self):
        from urllib.error import HTTPError
        calls = {"masry": 0}
        def fetch_rate_limited(url, limit):
            if "almasryalyoum" not in url:
                return feed_xml(HAPI_URL)
            calls["masry"] += 1
            raise HTTPError(url, 429, "rate-limited", {}, None)
        result = inspect(CONFIG, fetch=fetch_rate_limited, now=CURRENT)
        self.assertEqual(calls["masry"], 1)
        self.assertEqual([x["status"] for x in result["sources"]], ["ok", "failed"])
        self.assertEqual(result["sources"][1]["error"], "HTTPError")
        self.assertEqual(result["sources"][1]["http_status"], 429)
        self.assertEqual(result["planning_headline_matches"], 1)
        self.assertFalse(result["email_sent"])
        self.assertFalse(result["scheduler_enabled"])

    def test_rss_transient_503_recovers_with_only_one_same_url_retry(self):
        from urllib.error import HTTPError
        calls = {"masry": 0}
        def fetch_transient(url, limit):
            if "almasryalyoum" not in url:
                return feed_xml(HAPI_URL)
            calls["masry"] += 1
            if calls["masry"] == 1:
                raise HTTPError(url, 503, "source-unavailable", {}, None)
            return feed_xml(MASRY_URL)
        result = inspect(CONFIG, fetch=fetch_transient, now=CURRENT)
        self.assertEqual(calls["masry"], 2)
        self.assertEqual([x["status"] for x in result["sources"]], ["ok", "ok"])

    def test_transient_bad_rss_recovers_on_one_retry(self):
        calls = {"masry": 0}
        def fetch_once_bad(url, limit):
            if "almasryalyoum" not in url:
                return feed_xml(HAPI_URL)
            calls["masry"] += 1
            return b"not valid xml" if calls["masry"] == 1 else feed_xml(MASRY_URL)
        with patch("monitor.sleep") as delay:
            result = inspect(CONFIG, fetch=fetch_once_bad, now=CURRENT)
        delay.assert_called_once_with(1.25)
        self.assertEqual(calls["masry"], 2)
        self.assertTrue(result["sources"][1]["rss_parse_retry_delayed"])
        self.assertEqual([s["status"] for s in result["sources"]], ["ok", "ok"])
        self.assertEqual(result["planning_headline_matches"], 2)

    def test_second_invalid_original_xml_remains_failed_and_no_missing_story_fabricated(self):
        calls = {"masry": 0}
        def malformed_both_times(url, limit):
            if "almasryalyoum" not in url:
                return feed_xml(HAPI_URL)
            calls["masry"] += 1
            return b"<?xml version='1.0'?><rss><channel><item>"
        with patch("monitor.sleep") as delay:
            result = inspect(CONFIG, fetch=malformed_both_times, now=CURRENT)
        self.assertEqual(calls["masry"], 2)
        delay.assert_called_once_with(1.25)
        self.assertEqual(result["sources"][1]["status"], "failed")
        self.assertEqual(result["sources"][1]["error"], "ParseError")
        self.assertTrue(result["sources"][1]["xml_input_looked_like_rss"])
        self.assertFalse(result["sources"][1]["xml_input_looked_like_html"])
        self.assertTrue(result["sources"][1]["identical_bad_xml_on_retry"])
        self.assertIsInstance(result["sources"][1]["xml_error_code"], int)
        self.assertGreaterEqual(result["sources"][1]["xml_error_line"], 1)
        self.assertGreater(result["sources"][1]["malformed_rss_length"], 0)
        self.assertEqual(result["planning_headline_matches"], 1)
        self.assertTrue(result["sources"][1]["rss_parse_retry_delayed"])

    def test_second_different_bad_xml_records_not_identical_without_response_text(self):
        calls = {"masry": 0}
        def fetch_broken(url, limit):
            if "almasryalyoum" not in url:
                return feed_xml(HAPI_URL)
            calls["masry"] += 1
            return (b"<rss><channel><item>" if calls["masry"] == 1
                    else b"<rss><channel><other>")
        with patch("monitor.sleep") as delay:
            result = inspect(CONFIG, fetch=fetch_broken, now=CURRENT)
        self.assertEqual(calls["masry"], 2)
        self.assertFalse(result["sources"][1]["identical_bad_xml_on_retry"])
        self.assertEqual(result["sources"][1]["error"], "ParseError")
        delay.assert_called_once_with(1.25)
        self.assertNotIn("rss_payload", result["sources"][1])

    def test_xml_retry_never_repairs_malformed_publisher_items(self):
        calls = {"masry": 0}
        def still_bad(url, limit):
            if "almasryalyoum" not in url:
                return feed_xml(HAPI_URL)
            calls["masry"] += 1
            return "<rss><channel><item><title>وزارة التخطيط & fake</title></item></channel></rss>".encode("utf-8")
        with patch("monitor.sleep") as delay:
            result = inspect(CONFIG, fetch=still_bad, now=CURRENT)
        self.assertEqual(calls["masry"], 2)
        self.assertEqual(result["sources"][1]["status"], "failed")
        self.assertEqual(result["planning_headline_matches"], 1)
        delay.assert_called_once_with(1.25)

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

    def test_newest_article_is_selected_across_feeds_after_large_first_source(self):
        """News from the second publisher must not be hidden by RSS order."""
        old_items = "".join(
            f"<item><title>{HEADLINE} {index}</title>"
            f"<link>https://hapijournal.com/older-{index}</link>"
            "<pubDate>Tue, 13 Oct 2026 07:00:00 GMT</pubDate></item>"
            for index in range(18)
        )
        newest = (
            f"<item><title>{HEADLINE}</title><link>{MASRY_URL}</link>"
            "<pubDate>Tue, 13 Oct 2026 11:00:00 GMT</pubDate></item>"
        )
        def fetch(url, limit):
            if url == "https://hapijournal.com/feed/":
                return ("<rss><channel>" + old_items + "</channel></rss>").encode()
            return ("<rss><channel>" + newest + "</channel></rss>").encode()

        observed = inspect(CONFIG, fetch=fetch, now=CURRENT, article_limit=200)
        chosen = eligible_candidates(observed, CONFIG, CURRENT, limit=2)
        self.assertEqual(observed["planning_headline_matches"], 19)
        self.assertEqual(chosen[0]["url"], MASRY_URL)

        captured = []
        def capture(url, publisher, destination):
            captured.append(url)
            return {"ok": True, "actual_url": url, "title": HEADLINE}
        with patch.dict(os.environ, {}, clear=True):
            result = run("dry_run", fetch=fetch, capture=capture, clock=CURRENT)
        self.assertEqual(result["eligible"], 2)
        self.assertEqual(captured[0], MASRY_URL)
        self.assertEqual(result["smtp_accepted"], 0)

    def test_capture_failures_identify_source_without_raw_error_details(self):
        def fetch(url, limit):
            return feed_xml(HAPI_URL if "hapijournal" in url else MASRY_URL)

        def capture(url, publisher, destination):
            if publisher == "almasryalyoum.com":
                return {"ok": False,
                        "reason": "publisher_access_refused",
                        "private_body": "sensitive website response"}
            return {"ok": True, "actual_url": url, "title": HEADLINE}
        with patch.dict(os.environ, {}, clear=True):
            result = run("dry_run", fetch=fetch, capture=capture, clock=CURRENT)
        by_feed = {row["feed_id"]: row for row in result["capture_by_feed"]}
        self.assertEqual(by_feed["hapi"]["captured"], 1)
        self.assertEqual(by_feed["almasryalyoum"]["rejected"], 1)
        self.assertEqual(
            by_feed["almasryalyoum"]["rejection_reasons"],
            {"publisher_access_refused": 1})
        self.assertEqual(result["captured"], 1)
        self.assertEqual(result["rejected_capture"], 1)
        self.assertNotIn("sensitive website response", json.dumps(result))

    def test_no_automatic_capture_of_expired_native_publisher_story(self):
        feed = next(f for f in CONFIG["feeds"] if f["id"] == "almasryalyoum")
        _, matches = parse_rss(
            feed_xml(MASRY_URL, published="Sun, 01 Jan 2023 09:00:00 +0300"),
            feed, CONFIG["keywords"], now=CURRENT)
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
