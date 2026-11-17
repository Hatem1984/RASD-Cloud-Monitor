"""No-network pin for Daily News Egypt exact same-owner feed migration."""
import json
import unittest
from pathlib import Path

from capture_public import APPROVED_PUBLISHERS, allowed_url
from monitor import APPROVED_FEED_URLS, RejectRedirect


class DailyNewsEgyptDirectFeed(unittest.TestCase):
    def test_canonical_original_rss_and_same_article_hosts_only(self):
        cfg = json.loads(Path("sources_newsroom_active.json").read_text(
            encoding="utf-8"))
        self.assertEqual(len(cfg["feeds"]), 13)
        feed = next(x for x in cfg["feeds"] if x["id"] == "dailynewsegypt")
        self.assertEqual(feed["url"], "https://dailynewsegypt.com/feed/")
        self.assertEqual(set(feed["allowed_article_hosts"]),
                         {"dailynewsegypt.com", "www.dailynewsegypt.com"})
        self.assertIn(feed["url"], APPROVED_FEED_URLS)
        self.assertNotIn("https://www.dailynewsegypt.com/feed/",
                         APPROVED_FEED_URLS)
        self.assertEqual(
            APPROVED_PUBLISHERS["dailynewsegypt.com"],
            frozenset({"dailynewsegypt.com", "www.dailynewsegypt.com"}))
        self.assertTrue(allowed_url("https://dailynewsegypt.com/example",
                                    "dailynewsegypt.com"))
        self.assertTrue(allowed_url("https://www.dailynewsegypt.com/example",
                                    "dailynewsegypt.com"))
        self.assertFalse(allowed_url("https://cdndailynewsegypt.com/example",
                                     "dailynewsegypt.com"))
        self.assertFalse(allowed_url("http://dailynewsegypt.com/example",
                                     "dailynewsegypt.com"))

    def test_no_redirect_following_is_still_enforced(self):
        with self.assertRaisesRegex(RuntimeError, "feed_redirect_blocked"):
            RejectRedirect().redirect_request(
                None, None, 301, "Moved", {},
                "https://dailynewsegypt.com/feed/")


if __name__ == "__main__":
    unittest.main()
