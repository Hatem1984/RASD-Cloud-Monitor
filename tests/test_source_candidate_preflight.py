"""No-network candidate research tests. Synthetic RSS is never production evidence."""
import unittest
from datetime import datetime, timezone

from rasd_source_candidate_preflight import (
    audit_catalog, feed_candidates, inspect_candidate, same_publisher,
)


class ResearchCandidatePreflight(unittest.TestCase):
    NOW = datetime(2026, 11, 19, 18, 30, tzinfo=timezone.utc)
    ROW = {"id": "example_publisher", "name_ar": "ناشر مصطنع",
           "homepage_url": "https://example.org/",
           "publisher_host": "example.org"}

    def test_full_existing_catalog_is_offline_and_unapproved(self):
        def no_network(*_args):
            self.fail("offline audit must not read public network")
        data = audit_catalog(limit=100, live=False, fetch=no_network)
        self.assertEqual(data["sources_in_catalog"], 100)
        self.assertEqual(data["approved_production_inventory_unchanged"], 13)
        self.assertEqual(data["status_counts"], {"NOT_CHECKED_OFFLINE": 100})
        self.assertEqual(data["screenshot_verified_by_this_audit"], 0)
        self.assertFalse(data["production_mail_sent"])

    def test_original_publisher_only_and_no_cross_domain_rss(self):
        html = (b'<link rel="alternate" type="application/rss+xml" '
                b'href="https://external.example/feed/" />'
                b'<link rel="alternate" type="application/rss+xml" '
                b'href="/feed/" />')
        feeds = feed_candidates("https://example.org/", "example.org", html)
        self.assertEqual(feeds[0], "https://example.org/feed/")
        self.assertNotIn("https://external.example/feed/", feeds)
        self.assertFalse(same_publisher("http://example.org/feed/", "example.org"))
        self.assertFalse(same_publisher("https://example.org:444/feed/", "example.org"))
        self.assertFalse(same_publisher("https://user:pass@example.org/feed/", "example.org"))
        self.assertFalse(same_publisher("https://evil-example.org/feed/", "example.org"))

    def test_relevant_original_rss_still_requires_image_qa(self):
        rss = (b'<?xml version="1.0" encoding="utf-8"?>'
               b'<rss version="2.0"><channel><title>News</title>'
               b'<item><title>Egypt Ministry of Planning publishes a plan</title>'
               b'<link>https://example.org/news/2026/11/19/article</link>'
               b'<pubDate>Thu, 19 Nov 2026 18:00:00 +0000</pubDate>'
               b'</item></channel></rss>')
        def fake_fetch(url, _maximum):
            return b"<html></html>" if url == self.ROW["homepage_url"] else rss
        result = inspect_candidate(
            self.ROW, {}, ["Egypt Ministry of Planning"], self.NOW,
            fetch=fake_fetch)
        self.assertEqual(result["stage"], "RSS_MATCH_PENDING_ORIGINAL_PAGE_IMAGE_QA")
        self.assertEqual(result["matched_recent_items"], 1)
        self.assertEqual(result["matched_last_24_hours"], 1)
        self.assertEqual(result["matched_previous_complete_hour"], 0)
        self.assertFalse(result["production_approved"])

    def test_preceding_hour_rss_yield_is_not_screenshot_confirmation(self):
        rss = (b'<rss><channel><item>'
               b'<title>Egypt Ministry of Planning publishes its investment plan</title>'
               b'<link>https://example.org/news/17</link>'
               b'<pubDate>Thu, 19 Nov 2026 17:45:00 +0000</pubDate>'
               b'</item></channel></rss>')
        result = inspect_candidate(
            self.ROW, {}, ["Egypt Ministry of Planning"], self.NOW,
            fetch=lambda url, size: rss)
        self.assertEqual(result["stage"], "RSS_MATCH_PENDING_ORIGINAL_PAGE_IMAGE_QA")
        self.assertEqual(result["matched_previous_complete_hour"], 1)
        self.assertEqual(result["matched_last_24_hours"], 1)
        self.assertFalse(result["production_approved"])

    def test_missing_original_publisher_date_is_hold(self):
        rss = (b'<rss><channel><item><title>Egypt Ministry of Planning</title>'
               b'<link>https://example.org/news/1</link></item></channel></rss>')
        result = inspect_candidate(
            self.ROW, {}, ["Egypt Ministry of Planning"], self.NOW,
            fetch=lambda url, size: rss)
        self.assertEqual(result["stage"], "HOLD")
        self.assertEqual(result["matched_recent_items"], 0)


if __name__ == "__main__":
    unittest.main()
