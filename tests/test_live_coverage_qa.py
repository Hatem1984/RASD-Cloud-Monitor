"""Pure offline tests: source coverage QA never sends or invents evidence."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from monitor import article_id
from rasd_live_coverage_qa import run_coverage_qa

NOW = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)
FEEDS = [
    {"id": "first", "name": "Original QA Publisher A"},
    {"id": "second", "name": "Original QA Publisher B"},
]
CONFIG = {"feeds": FEEDS}


def observation(*, healthy, matched=None):
    return {
        "sources": [
            {"feed_id": "first", "status": "ok", "verified_links": 5,
             "headline_matches": len(matched or [])},
            {"feed_id": "second", "status": "ok" if healthy else "failed",
             "verified_links": 7 if healthy else 0, "headline_matches": 0,
             "error": "HTTPError" if not healthy else None,
             "http_status": 403 if not healthy else None},
        ],
        "matched_public_articles": matched or [],
    }


class LiveCoverageContract(unittest.TestCase):
    def test_all_sources_mentioned_even_if_one_refused_and_no_news(self):
        def inspect(_config, **kwargs):
            self.assertEqual(kwargs["article_limit"], 200)
            self.assertTrue(kwargs["require_complete_items"])
            return observation(healthy=False)
        result = run_coverage_qa(CONFIG, inspector=inspect, now=NOW,
                                 max_attempts=0)
        self.assertEqual(result["checked_sources"], 2)
        self.assertEqual(result["failed_sources"], 1)
        self.assertEqual(result["sources"][1]["id"], "second")
        self.assertEqual(result["sources"][1]["http_status"], 403)
        self.assertEqual(result["capture_attempts"], 0)
        self.assertFalse(result["email_sent"])
        self.assertFalse(result["new_production_sources_activated"])
        self.assertEqual(result["status"], "DEGRADED_OR_PARTIAL")

    def test_no_fake_screenshots_when_publisher_refuses(self):
        url = "https://original.example/story"
        matched = [{"source": "Original QA Publisher A", "url": url,
                    "headline": "وزارة التخطيط تعلن تفاصيل مبادرة تنموية جديدة",
                    "published": "Tue, 17 Nov 2026 07:00:00 +0000"}]
        article = {"id": article_id(url), "url": url,
                   "source": "Original QA Publisher A",
                   "headline": matched[0]["headline"],
                   "published_at_cairo": "2026-11-17 09:00 EET",
                   "published_display_cairo": "17 نوفمبر 2026"}
        with patch("rasd_live_coverage_qa.candidate_from_feed",
                   return_value=article):
            result = run_coverage_qa(
                CONFIG, inspector=lambda *_a, **_k: observation(
                    healthy=True, matched=matched),
                capture=lambda *_a, **_k: {
                    "status": "hold", "reason": "publisher_access_refused"},
                now=NOW, max_attempts=1)
        self.assertEqual(result["capture_attempts"], 1)
        self.assertEqual(result["verified_original_screenshots"], 0)
        self.assertEqual(result["capture_receipts"][0]["status"], "HOLD")
        self.assertFalse(result["ephemeral_original_word_image_binding_verified"])

    def test_untrusted_exception_text_not_logged(self):
        url = "https://original.example/story"
        candidate = {"id": article_id(url), "url": url,
                     "source": "Original QA Publisher A",
                     "headline": "وزارة التخطيط تعلن تفاصيل مبادرة تنموية جديدة",
                     "published": "Tue, 17 Nov 2026 07:00:00 +0000"}
        with patch("rasd_live_coverage_qa.candidate_from_feed",
                   return_value=candidate):
            result = run_coverage_qa(
                CONFIG, inspector=lambda *_a, **_k: observation(
                    healthy=True, matched=[candidate]),
                capture=lambda *_a, **_k: {
                    "status": "hold", "reason":
                    "token=DO_NOT_LOG https://private.example"},
                now=NOW, max_attempts=1)
        self.assertEqual(result["capture_receipts"][0]["reason"], "other")

    def test_invalid_source_inventory_stops_before_network(self):
        untrusted = {"feeds": [
            {"id": "bad\nsecret", "name": "injected"}]}
        with self.assertRaises(ValueError):
            run_coverage_qa(untrusted, inspector=lambda *_a, **_k:
                            self.fail("should never fetch"), now=NOW)

    def test_strict_monitor_exposes_only_preapproved_feed_error_code(self):
        from monitor import inspect

        config = {
            "feeds": [
                {"id": "hapi", "name": "Hapi", "url": "https://hapijournal.com/feed/",
                 "allowed_article_hosts": ["hapijournal.com"]},
                {"id": "broken", "name": "Broken QA", "url": "https://broken.invalid/feed",
                 "allowed_article_hosts": ["broken.invalid"]},
            ],
            "keywords": ["وزارة التخطيط"],
            "max_feed_bytes": 100000,
            "recent_hours": 72,
        }
        fixture = (
            '<rss><channel><item><title>وزارة التخطيط تعلن برنامجًا جديدًا</title>'
            '<link>https://hapijournal.com/qa-story</link>'
            '<pubDate>Tue, 17 Nov 2026 07:00:00 +0000</pubDate>'
            '</item></channel></rss>').encode()
        def fetch(url, _limit):
            if "broken.invalid" in url:
                raise RuntimeError("feed_redirect_blocked")
            return fixture
        result = inspect(config, fetch=fetch, now=NOW,
                         require_complete_items=True, article_limit=200)
        self.assertEqual(result["sources"][1]["error"], "RuntimeError")
        self.assertEqual(result["sources"][1]["error_code"],
                         "feed_redirect_blocked")

    def test_untrusted_feed_error_message_replaced_with_other(self):
        from monitor import inspect
        config = {
            "feeds": [
                {"id": "first", "name": "Hapi", "url": "https://hapijournal.com/feed/",
                 "allowed_article_hosts": ["hapijournal.com"]},
                {"id": "second", "name": "Broken", "url": "https://blocked.invalid/feed",
                 "allowed_article_hosts": ["blocked.invalid"]},
            ],
            "keywords": [],
            "max_feed_bytes": 100000,
            "recent_hours": 72,
        }
        fixture = (b'<rss><channel><item><title>Normal news</title>'
                   b'<link>https://hapijournal.com/story</link>'
                   b'<pubDate>Tue, 17 Nov 2026 07:00:00 +0000</pubDate>'
                   b'</item></channel></rss>')
        def fetch(url, _limit):
            if "blocked.invalid" in url:
                raise ValueError("secret=DO_NOT_EXPOSE http://private.invalid")
            return fixture
        result = inspect(config, fetch=fetch, now=NOW,
                         require_complete_items=True)
        self.assertEqual(result["sources"][1]["error_code"], "other")


if __name__ == "__main__":
    unittest.main()
