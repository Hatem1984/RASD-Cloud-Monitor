"""Reviewable source failure classification; offline fixtures, no live requests."""
import unittest
from datetime import datetime,timezone
from urllib.error import HTTPError,URLError
from unittest.mock import patch
import monitor

class SourceReasons(unittest.TestCase):
    def test_known_redirect_and_missing_original_date_are_explicit(self):
        self.assertEqual(monitor.safe_source_failure_code(
            RuntimeError("feed_redirect_blocked")),"feed_redirect_blocked")
        self.assertEqual(monitor.safe_source_failure_code(
            ValueError("rss_original_item_date_unverifiable")),
            "rss_original_item_date_unverifiable")
    def test_arbitrary_publisher_text_is_never_logged(self):
        e=RuntimeError("PRIVATE_PASSWORD_BROKEN_1999")
        code=monitor.safe_source_failure_code(e)
        self.assertEqual(code,"unclassified_source_failure")
        self.assertNotIn("PRIVATE_PASSWORD",code)
    def test_http_status_and_network_codes_are_safe(self):
        self.assertEqual(monitor.safe_source_failure_code(HTTPError(
            "https://source.example",429,"rate limit",None,None)),"publisher_rate_limited")
        self.assertEqual(monitor.safe_source_failure_code(
            URLError("PRIVATE_TOKEN_BROKEN_1999")),"source_transport_unavailable")
    def test_inspect_tracks_healthy_and_exact_hold_without_article_leak(self):
        feeds=[{"id":"good","url":"good"},{"id":"redirect","url":"redirect"},
               {"id":"bad-date","url":"bad-date"}]
        config={"feeds":feeds,"max_feed_bytes":1000,"keywords":["وزارة التخطيط"],
                "recent_hours":2}
        def fetch(url,limit):
            if url=="redirect":raise RuntimeError("feed_redirect_blocked")
            return url.encode()
        def parse(raw,*args,**kwargs):
            if raw==b"bad-date":raise ValueError("rss_original_item_date_unverifiable")
            return (1,[])
        with patch.object(monitor,"parse_rss",side_effect=parse):
            r=monitor.inspect(config,fetch=fetch,now=datetime(2026,11,3,12,0,tzinfo=timezone.utc))
        self.assertEqual([x["status"] for x in r["sources"]],["ok","failed","failed"])
        self.assertNotIn("failure_code",r["sources"][0])
        self.assertEqual(r["sources"][1]["failure_code"],"feed_redirect_blocked")
        self.assertEqual(r["sources"][2]["failure_code"],"rss_original_item_date_unverifiable")
        self.assertEqual(r["planning_headline_matches"],0)
        self.assertFalse(r["email_sent"])

if __name__=="__main__":unittest.main()
