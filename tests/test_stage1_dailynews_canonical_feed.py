"""Same-publisher canonical feed repair contracts, offline only."""
import json
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from monitor import APPROVED_FEED_URLS,read_feed,parse_rss
from capture_public import allowed_url
from monitor import article_id
ROOT=Path(__file__).resolve().parents[1]
CANONICAL="https://dailynewsegypt.com/feed/"
REDIRECTING="https://www.dailynewsegypt.com/feed/"

class DailyNewsSamePublisher(unittest.TestCase):
    def setUp(self):
        self.owner=json.loads((ROOT/"sources_owner_daily_qa.json").read_text("utf-8"))
        self.active=json.loads((ROOT/"sources_newsroom_active.json").read_text("utf-8"))
    def test_same_original_feed_endpoint_in_both_settings(self):
        for conf in (self.owner,self.active):
            f=next(x for x in conf["feeds"] if x["id"]=="dailynewsegypt")
            self.assertEqual(f["url"],CANONICAL)
            self.assertEqual(set(f["allowed_article_hosts"]),
                             {"dailynewsegypt.com","www.dailynewsegypt.com"})
        self.assertIn(CANONICAL,APPROVED_FEED_URLS)
        self.assertNotIn(REDIRECTING,APPROVED_FEED_URLS)
    def test_no_arbitrary_domain_or_scheme_accepted(self):
        self.assertTrue(allowed_url("https://dailynewsegypt.com/first-party-original","dailynewsegypt.com"))
        self.assertTrue(allowed_url("https://www.dailynewsegypt.com/first-party-original","dailynewsegypt.com"))
        for u in ("http://dailynewsegypt.com/a",
                  "https://dailynewsegypt.com.evil.invalid/a",
                  "https://dailynewsegypt.com:8080/a",
                  "https://other.example/a"):
            self.assertFalse(allowed_url(u,"dailynewsegypt.com"))
    def test_publisher_rss_canonical_link_parses_without_changed_clock(self):
        source=next(x for x in self.owner["feeds"] if x["id"]=="dailynewsegypt")
        link="https://dailynewsegypt.com/verified-canonical-original-article/"
        xml=(f"<rss><channel><item><title>Planning minister announces a programme</title>"
             f"<link>{link}</link><pubDate>Tue, 03 Nov 2026 12:00:00 +0200</pubDate>"
             "</item></channel></rss>").encode()
        got,articles=parse_rss(xml,source,["Planning minister"],
                               now=datetime(2026,11,3,10,15,tzinfo=timezone.utc),
                               require_complete_items=True)
        self.assertEqual(got,1)
        self.assertEqual(len(articles),1)
        self.assertEqual(articles[0]["id"],article_id(link))
        self.assertEqual(articles[0]["published"],"Tue, 03 Nov 2026 12:00:00 +0200")
    def test_old_redirecting_endpoint_rejected_before_network(self):
        with patch("monitor.build_opener") as op:
            with self.assertRaisesRegex(ValueError,"feed_endpoint_not_reviewed"):
                read_feed(REDIRECTING,1000)
            op.assert_not_called()

if __name__=="__main__":unittest.main()
