"""Offline security and discovery tests for public RSS worker."""
import unittest
from datetime import datetime, timezone
from monitor import article_id, inspect, is_publisher_link, parse_rss


FEED = {"id": "hapi", "name": "Hapi native RSS",
        "url": "https://hapijournal.com/feed/",
        "allowed_article_hosts": ["hapijournal.com", "www.hapijournal.com"]}
CONFIG = {"feeds": [FEED], "keywords": ["وزارة التخطيط", "وزير التخطيط"],
          "max_feed_bytes": 1500000, "recent_hours": 72}
NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)


def item(title, url, date="Tue, 13 Oct 2026 07:00:00 GMT"):
    return (f"<item><title>{title}</title><link>{url}</link>"
            f"<pubDate>{date}</pubDate></item>")


def rss(*entries):
    return ('<rss version="2.0"><channel>' + "".join(entries) +
            '</channel></rss>').encode("utf-8")


class PublicMonitoringTests(unittest.TestCase):
    def test_strict_domain_and_port(self):
        self.assertTrue(is_publisher_link("https://hapijournal.com/story", FEED["allowed_article_hosts"]))
        for url in ("http://hapijournal.com/story", "https://hapijournal.com:8443/story",
                    "https://hapijournal.com.evil.example/story",
                    "https://user:pass@hapijournal.com/story",
                    "https://news.google.com/rss/articles/x"):
            with self.subTest(url=url):
                self.assertFalse(is_publisher_link(url, FEED["allowed_article_hosts"]))

    def test_real_publisher_headline_is_matched(self):
        count, matches = parse_rss(
            rss(item("وزير التخطيط يعلن خطة جديدة", "https://hapijournal.com/a")),
            FEED, CONFIG["keywords"], now=NOW)
        self.assertEqual(count, 1)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], article_id("https://hapijournal.com/a"))

    def test_aggregators_cannot_be_accepted(self):
        count, matches = parse_rss(
            rss(item("وزير التخطيط", "https://news.google.com/rss/articles/123")),
            FEED, CONFIG["keywords"], now=NOW)
        self.assertEqual((count, len(matches)), (0, 0))

    def test_other_topics_not_notified(self):
        count, matches = parse_rss(
            rss(item("البورصة المصرية اليوم", "https://hapijournal.com/a")),
            FEED, CONFIG["keywords"], now=NOW)
        self.assertEqual((count, len(matches)), (1, 0))

    def test_stale_news_not_alerted(self):
        count, matches = parse_rss(
            rss(item("وزير التخطيط", "https://hapijournal.com/a",
                     "Tue, 13 Oct 2020 07:00:00 GMT")), FEED,
            CONFIG["keywords"], now=NOW)
        self.assertEqual((count, len(matches)), (1, 0))

    def test_duplicate_urls_collapsed(self):
        count, matches = parse_rss(rss(
            item("وزير التخطيط", "https://hapijournal.com/a?utm_source=x"),
            item("وزير التخطيط", "https://hapijournal.com/a")), FEED,
            CONFIG["keywords"], now=NOW)
        self.assertEqual((count, len(matches)), (2, 1))

    def test_xml_entity_forbidden(self):
        with self.assertRaisesRegex(ValueError, "DTD_or_entity_forbidden"):
            parse_rss(b'<!DOCTYPE foo><rss></rss>', FEED, CONFIG["keywords"], now=NOW)

    def test_naive_clock_fails_before_any_feed_fetch(self):
        from datetime import datetime
        naive = datetime(2026, 10, 13, 12, 0, 0)
        def never_fetch(*args):
            self.fail("naive clock must never trigger a publisher request")
        with self.assertRaisesRegex(ValueError, "naive_monitor_clock_forbidden"):
            inspect(CONFIG, fetch=never_fetch, now=naive)
        with self.assertRaisesRegex(ValueError, "naive_monitor_clock_forbidden"):
            parse_rss(rss(), FEED, CONFIG["keywords"], now=naive)

    def test_partial_outage_does_not_hide_healthy_source(self):
        cfg = {**CONFIG, "feeds": [{**FEED, "id": "fail"}, FEED]}
        def fetch(url, max_size):
            nonlocal attempt
            attempt += 1
            if attempt <= 2:
                raise TimeoutError("simulated persistent two-attempt publisher outage")
            return rss(item("وزارة التخطيط تعقد اجتماعا", "https://hapijournal.com/a"))
        attempt = 0
        result = inspect(cfg, fetch=fetch, now=NOW)
        self.assertEqual([s["status"] for s in result["sources"]], ["failed", "ok"])
        self.assertEqual(result["planning_headline_matches"], 1)
        self.assertFalse(result["email_sent"])
        self.assertFalse(result["scheduler_enabled"])

    def test_all_feeds_outage_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "all_public_RSS_sources_failed"):
            inspect(CONFIG, fetch=lambda url, max_size: b"<invalid", now=NOW)

    def test_fresh_feed_zero_matches_is_not_fabricated(self):
        result = inspect(CONFIG, fetch=lambda url, max_size: rss(
            item("بورصة اليوم", "https://hapijournal.com/market")), now=NOW)
        self.assertEqual(result["planning_headline_matches"], 0)
        self.assertEqual(result["matched_public_articles"], [])


if __name__ == "__main__":
    unittest.main()
