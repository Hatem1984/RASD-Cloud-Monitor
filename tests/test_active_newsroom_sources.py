"""Strict production newsroom publisher profile contract; no Gmail or network."""
import json
import unittest
from pathlib import Path

from capture_public import APPROVED_PUBLISHERS, allowed_url
from monitor import APPROVED_FEED_URLS


ROOT = Path(__file__).resolve().parents[1]


class ActiveNewsroomProfile(unittest.TestCase):
    def test_three_original_publisher_rss_feeds_are_existing_reviewed_profiles(self):
        a = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
        s = json.loads((ROOT / "sources_shorouk.json").read_text(encoding="utf-8"))
        active = json.loads((ROOT / "sources_newsroom_active.json").read_text(encoding="utf-8"))
        # Keep existing owner-approved terms untouched; expanded phrases
        # are production terms but NEW publisher candidates remain QA-only.
        self.assertEqual(active["keywords"][:len(a["keywords"])], a["keywords"])
        self.assertEqual(active["keywords"][:len(s["keywords"])], s["keywords"])
        self.assertEqual(len(active["keywords"]), 18)
        self.assertEqual(len(set(active["keywords"])), 18)
        self.assertEqual(active["feeds"][:2], a["feeds"])
        self.assertEqual(active["feeds"][2:3], s["feeds"])
        self.assertEqual(active["feeds"][3]["id"], "alborsa")
        self.assertEqual([x["id"] for x in active["feeds"]],
                         ["hapi", "almasryalyoum", "shorouk", "alborsa"])
        self.assertEqual(active["recent_hours"], a["recent_hours"])
        self.assertEqual(active["max_feed_bytes"], a["max_feed_bytes"])
        self.assertEqual(len(active["feeds"]), 4)
        for item in active["feeds"]:
            self.assertIn(item["url"], APPROVED_FEED_URLS)
            self.assertTrue(item["url"].startswith("https://"))
            self.assertTrue(all(
                domain in {"hapijournal.com", "www.hapijournal.com",
                           "almasryalyoum.com", "www.almasryalyoum.com",
                           "www.shorouknews.com", "www.alborsaanews.com",
                           "alborsaanews.com"}
                for domain in item["allowed_article_hosts"]))

    def test_original_shorouk_page_is_an_approved_newsroom_publisher(self):
        url = "https://www.shorouknews.com/news/view.aspx?id=fixture"
        self.assertIn("shorouknews.com", APPROVED_PUBLISHERS)
        self.assertTrue(allowed_url(url, "shorouknews.com"))
        self.assertFalse(allowed_url("https://mped.gov.eg/singlenews?id=1",
                                     "shorouknews.com"))

    def test_no_railway_dependency_or_unreviewed_external_feed(self):
        active = json.loads((ROOT / "sources_newsroom_active.json").read_text(encoding="utf-8"))
        self.assertNotIn("railway", json.dumps(active).lower())
        self.assertEqual(len({x["url"] for x in active["feeds"]}), 4)


if __name__ == "__main__":
    unittest.main()
