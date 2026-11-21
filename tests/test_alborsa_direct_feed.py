"""No-network regression for exact first-party Alborsa feed migration."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from monitor import APPROVED_FEED_URLS, RejectRedirect


class AlborsaDirectFeed(unittest.TestCase):
    def test_direct_publisher_exact_url_and_same_original_article_host_scope(self):
        config = json.loads(Path("sources_newsroom_active.json").read_text(
            encoding="utf-8"))
        self.assertEqual(len(config["feeds"]), 14)
        feed = next(f for f in config["feeds"] if f["id"] == "alborsa")
        expected = ("https://alborsaanews.com/category/"
                    "%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-"
                    "%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%89/feed")
        self.assertEqual(feed["url"], expected)
        self.assertIn(expected, APPROVED_FEED_URLS)
        self.assertNotIn(expected.replace("https://alborsaanews.com/",
                                         "https://www.alborsaanews.com/"),
                         APPROVED_FEED_URLS)
        self.assertEqual(urlsplit(expected).hostname, "alborsaanews.com")
        self.assertEqual(set(feed["allowed_article_hosts"]),
                         {"alborsaanews.com", "www.alborsaanews.com"})
        self.assertEqual(feed["name"], "Alborsa native Egyptian Economy RSS")

    def test_reject_redirect_policy_stays_active(self):
        with self.assertRaisesRegex(RuntimeError, "feed_redirect_blocked"):
            RejectRedirect().redirect_request(
                None, None, 301, "Moved", {}, "https://outside.invalid/")


if __name__ == "__main__":
    unittest.main()
