"""Offline regression for approved-public-RSS diagnostics.

No feed, SMTP, private ledger or screenshot network access.
"""
from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone

from scheduled_rasd import (
    discover_interval_news,
    public_failed_feed_diagnostics,
)


class SafeScheduledSourceDiagnostics(unittest.TestCase):
    def setUp(self):
        self.feeds = [{"id": "hapi"}, {"id": "dailynewsegypt"}]
        self.config = {"feeds": self.feeds, "keywords": [],
                       "recent_hours": 72}

    def test_failed_source_identity_and_allowlisted_class_only(self):
        rows = [
            {"feed_id": "hapi", "status": "ok", "verified_links": 10},
            {"feed_id": "dailynewsegypt", "status": "failed",
             "error": "RuntimeError", "http_status": None,
             "untrusted_url": "https://example.invalid/hidden"},
        ]
        self.assertEqual(public_failed_feed_diagnostics(rows, self.feeds), [
            {"feed_id": "dailynewsegypt", "error_type": "RuntimeError",
             "http_status": None}
        ])

    def test_untrusted_error_text_and_unapproved_status_are_suppressed(self):
        rows = [
            {"feed_id": "hapi", "status": "failed",
             "error": "HTTPError: secret@example.com /private?token=123",
             "http_status": "403", "response_body": "PRIVATE"},
            {"feed_id": "dailynewsegypt", "status": "failed",
             "error": "HTTPError", "http_status": 403},
        ]
        result = public_failed_feed_diagnostics(rows, self.feeds)
        encoded = json.dumps(result, ensure_ascii=True)
        self.assertEqual(result, [
            {"feed_id": "hapi", "error_type": "other", "http_status": None},
            {"feed_id": "dailynewsegypt", "error_type": "HTTPError",
             "http_status": 403},
        ])
        for forbidden in ("secret@example.com", "token=123", "PRIVATE"):
            self.assertNotIn(forbidden, encoded)

    def test_invalid_identity_or_feed_order_does_not_leak(self):
        rows = [
            {"feed_id": "hapi", "status": "failed", "error": "URLError"},
            {"feed_id": "dailynewsegypt\nLEAK_SECRET",
             "status": "failed", "error": "RuntimeError"},
        ]
        self.assertEqual(public_failed_feed_diagnostics(rows, self.feeds), [])
        rows[1]["feed_id"] = "dailynewsegypt"
        self.assertEqual(len(public_failed_feed_diagnostics(rows, self.feeds)), 2)

    def test_live_scheduler_scan_writes_only_bounded_source_line(self):
        sources = [
            {"feed_id": "hapi", "status": "ok", "verified_links": 5},
            {"feed_id": "dailynewsegypt", "status": "failed",
             "verified_links": 0, "error": "HTTPError", "http_status": 301,
             "private_data": "DO_NOT_LOG_THIS"},
        ]
        def fake_inspector(*args, **kwargs):
            return {"sources": sources, "matched_public_articles": [],
                    "matched_article_pool_truncated": False}
        records = []
        output = io.StringIO()
        with redirect_stdout(output):
            selected = discover_interval_news(
                self.config, datetime(2026, 11, 9, 12, tzinfo=timezone.utc),
                inspector=fake_inspector, allow_degraded=True,
                source_records=records)
        self.assertEqual(selected, [])
        self.assertEqual(len(records), 2)
        self.assertNotIn("error", records[1])
        log = output.getvalue()
        self.assertIn("RASD_APPROVED_RSS_SOURCE_FAILURES=", log)
        self.assertIn('"feed_id": "dailynewsegypt"', log)
        self.assertIn('"http_status": 301', log)
        self.assertNotIn("DO_NOT_LOG_THIS", log)
        self.assertNotIn("https://", log)

    def test_all_healthy_unchanged_and_no_extra_log(self):
        sources = [
            {"feed_id": "hapi", "status": "ok", "verified_links": 10},
            {"feed_id": "dailynewsegypt", "status": "ok",
             "verified_links": 10},
        ]
        def fake_inspector(*args, **kwargs):
            return {"sources": sources, "matched_public_articles": [],
                    "matched_article_pool_truncated": False}
        output = io.StringIO()
        with redirect_stdout(output):
            result = discover_interval_news(
                self.config, datetime(2026, 11, 9, 12, tzinfo=timezone.utc),
                inspector=fake_inspector, allow_degraded=True,
                source_records=[])
        self.assertEqual(result, [])
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
