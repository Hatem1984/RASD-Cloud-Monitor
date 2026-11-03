"""Offline regression: only the direct first-party Al Borsa category RSS."""
import json
import unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from monitor import APPROVED_FEED_URLS,parse_rss,read_feed
from capture_public import allowed_url

ROOT=Path(__file__).resolve().parents[1]
PATH="category/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%89/feed"
ORIGIN="https://alborsaanews.com/"+PATH
REDIRECT="https://www.alborsaanews.com/"+PATH

class AlBorsaDirectPublisher(unittest.TestCase):
    def setUp(self):
        self.configs=[json.loads((ROOT/f).read_text(encoding="utf-8"))
                      for f in ("sources_owner_daily_qa.json","sources_newsroom_active.json")]
    def test_two_profiles_point_to_one_reviewed_exact_publisher_endpoint(self):
        for cfg in self.configs:
            f=next(x for x in cfg["feeds"] if x["id"]=="alborsa")
            self.assertEqual(f["url"],ORIGIN)
            self.assertEqual(set(f["allowed_article_hosts"]),
                             {"alborsaanews.com","www.alborsaanews.com"})
        self.assertIn(ORIGIN,APPROVED_FEED_URLS)
        self.assertNotIn(REDIRECT,APPROVED_FEED_URLS)
    def test_no_open_redirect_following_or_third_party_feed(self):
        with patch("monitor.build_opener") as opens:
            for url in (REDIRECT,ORIGIN+"?redirect=https://evil.invalid",
                        "https://alborsaanews.com.evil.invalid/"+PATH,
                        "http://alborsaanews.com/"+PATH):
                with self.assertRaisesRegex(ValueError,"feed_endpoint_not_reviewed"):
                    read_feed(url,1000)
            opens.assert_not_called()
    def test_article_host_guards_remain_exact(self):
        self.assertTrue(allowed_url("https://alborsaanews.com/2026/11/03/12345","alborsaanews.com"))
        self.assertTrue(allowed_url("https://www.alborsaanews.com/2026/11/03/12345","alborsaanews.com"))
        self.assertFalse(allowed_url("https://alborsaanews.com.evil.invalid/abc","alborsaanews.com"))
    def test_owner_date_is_not_inferred(self):
        f=next(x for x in self.configs[0]["feeds"] if x["id"]=="alborsa")
        url="https://alborsaanews.com/2026/11/03/test"
        xml=(f"<rss><channel><item><title>وزير التخطيط يتابع مشروعًا</title>"
             f"<link>{url}</link><pubDate>Tue, 03 Nov 2026 18:00:00 +0200</pubDate>"
             "</item></channel></rss>").encode()
        count,matches=parse_rss(xml,f,["وزير التخطيط"],
                                datetime(2026,11,3,16,30,tzinfo=timezone.utc),
                                require_complete_items=True)
        self.assertEqual(count,1)
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]["published"],"Tue, 03 Nov 2026 18:00:00 +0200")

if __name__=="__main__":unittest.main()
