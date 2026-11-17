"""Source failures are actionable without emitting untrusted publisher errors.

No network, SMTP, private ledger, or schedule. A source is never labelled
healthy merely because an error class was recognized.
"""
import unittest
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET

import scheduled_rasd as worker
from monitor import SOURCE_FAILURE_CODES, inspect, safe_source_failure_code

NOW = datetime(2026, 11, 17, 17, tzinfo=timezone.utc)
FEEDS = [
    {"id": "first", "name": "One", "url": "https://one.example/rss",
     "allowed_article_hosts": ["one.example"]},
    {"id": "second", "name": "Two", "url": "https://two.example/rss",
     "allowed_article_hosts": ["two.example"]},
]
CONFIG = {"feeds": FEEDS, "max_feed_bytes": 1_000_000, "recent_hours": 72,
          "keywords": ["وزارة التخطيط"]}
XML = (b'<rss><channel><item><title>Normal news</title>'
       b'<link>https://one.example/news/1</link>'
       b'<pubDate>Tue, 17 Nov 2026 15:00:00 +0000</pubDate>'
       b'</item></channel></rss>')


class SafeSourceFailureReasonsQA(unittest.TestCase):
    def test_exact_internal_codes_only(self):
        self.assertEqual(safe_source_failure_code(
            ValueError("rss_original_item_date_unverifiable")),
            "rss_original_item_date_unverifiable")
        self.assertEqual(safe_source_failure_code(
            RuntimeError("feed_redirect_blocked")), "feed_redirect_blocked")
        self.assertEqual(safe_source_failure_code(
            RuntimeError("token=SECRET https://private.invalid")), "other")
        self.assertEqual(safe_source_failure_code(
            ValueError("http_403 secret=SECRET")), "other")
        self.assertNotIn("SECRET", str(SOURCE_FAILURE_CODES))

    def test_http_and_xml_failure_codes_are_bounded(self):
        e = HTTPError("https://secret.invalid/", 403, "secret",
                      None, None)
        self.assertEqual(safe_source_failure_code(e), "http_403")
        self.assertEqual(safe_source_failure_code(
            HTTPError("https://secret.invalid/", 418, "secret", None, None)),
            "other")
        self.assertEqual(safe_source_failure_code(URLError("secret")),
                         "upstream_network_error")
        try:
            ET.fromstring(b"<rss><channel><item>")
        except ET.ParseError as err:
            self.assertEqual(safe_source_failure_code(err),
                             "rss_xml_malformed")

    def test_inspect_exposes_code_but_never_upstream_exception_string(self):
        def fetch(url, _limit):
            if "two.example" in url:
                raise RuntimeError("feed_redirect_blocked")
            return XML
        info = inspect(CONFIG, fetch=fetch, now=NOW,
                       require_complete_items=True)
        self.assertEqual(info["sources"][0]["status"], "ok")
        self.assertNotIn("error_code", info["sources"][0])
        self.assertEqual(info["sources"][1]["status"], "failed")
        self.assertEqual(info["sources"][1]["error_code"],
                         "feed_redirect_blocked")
        self.assertEqual(info["sources"][1]["error"], "RuntimeError")

    def test_diagnostics_survive_to_no_send_production_status(self):
        def fake_inspector(config, **kwargs):
            return {"sources": [
                {"feed_id": "first", "status": "ok", "verified_links": 1},
                {"feed_id": "second", "status": "failed",
                 "error": "ValueError",
                 "error_code": "rss_original_item_date_unverifiable",
                 "verified_links": 0},
            ], "matched_public_articles": [], "matched_article_pool_truncated":False}
        health = []
        news = worker.discover_interval_news(
            CONFIG, NOW, inspector=fake_inspector, allow_degraded=True,
            source_records=health)
        self.assertEqual(news, [])
        result = worker.smart_interval_no_mail(
            config=CONFIG, health=health, window="2026-11-17T17:00Z")
        self.assertEqual(result["status"],
                         "SOURCE_UNAVAILABLE_NO_VERIFIED_NEWS")
        self.assertEqual(result["failed_source_ids"], ["second"])
        self.assertEqual(result["failed_source_reasons"],
                         {"second": "rss_original_item_date_unverifiable"})
        self.assertFalse(result["smtp_accepted"])
        self.assertFalse(result["cas_mutated"])

    def test_untrusted_cause_must_stop_before_logging(self):
        health = [
            {"feed_id":"first", "status":"ok"},
            {"feed_id":"second", "status":"failed",
             "failure_code":"password=SECRET https://internal.invalid/"},
        ]
        with self.assertRaisesRegex(RuntimeError,
                                     "source_health_failure_code_untrusted"):
            worker.smart_interval_no_mail(
                config=CONFIG, health=health,
                window="2026-11-17T17:00Z")

    def test_absent_source_diagnosis_uses_other(self):
        health = [
            {"feed_id":"first", "status":"ok"},
            {"feed_id":"second", "status":"failed"},
        ]
        result = worker.smart_interval_no_mail(
            config=CONFIG, health=health, window="2026-11-17T17:00Z")
        self.assertEqual(result["failed_source_reasons"], {"second":"other"})


if __name__ == "__main__":
    unittest.main()
