"""RASD top-50 newsroom research contract; offline/no SMTP/no web."""
import json
import unittest
from pathlib import Path

from research_source_queries import load_registry, build_query, generate_queries

ROOT = Path(__file__).resolve().parents[1]


class TopFiftyResearchSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_registry()
        cls.sources = cls.data["sources"]
        cls.active = json.loads((ROOT / "sources_newsroom_active.json").read_text("utf-8"))

    def test_exactly_50_ranked_unique_origins_and_named_national_papers_first(self):
        self.assertEqual(len(self.sources), 50)
        self.assertEqual([x["priority"] for x in self.sources], list(range(1, 51)))
        self.assertEqual(len({x["id"] for x in self.sources}), 50)
        self.assertEqual(len({x["homepage_url"] for x in self.sources}), 50)
        self.assertEqual([x["name_ar"] for x in self.sources[:4]],
                         ["الأهرام", "أخبار اليوم / الأخبار", "الجمهورية", "المساء"])

    def test_real_approved_feeds_only_and_no_shadow_production_activation(self):
        active_ids = {x["id"] for x in self.active["feeds"]}
        catalog_ids = {x["id"] for x in self.sources if x["research_status"] == "active_native_rss"}
        self.assertEqual(catalog_ids, active_ids)
        self.assertEqual(len(catalog_ids), 5)
        self.assertEqual(sum(x["research_status"] == "candidate_not_scheduled"
                             for x in self.sources), 45)
        self.assertEqual(len(self.active["feeds"]), 5)
        self.assertEqual(len(self.active["keywords"]), 24)
        self.assertEqual(sum(x["rss_status"] == "approved_in_sources_newsroom_active.json"
                             for x in self.sources), 5)

    def test_measured_audience_rank_is_only_exact_published_top_five(self):
        published = {"youm7": 1, "masrawy": 2, "elbalad": 3,
                     "almasryalyoum": 4, "elwatan": 5}
        self.assertEqual({x["id"]: x["similarweb_egypt_news_rank_aug_2026"]
                          for x in self.sources
                          if x["similarweb_egypt_news_rank_aug_2026"] is not None},
                         published)

    def test_official_evidence_separate_from_press_and_syndication_is_not_certification(self):
        self.assertEqual([x["category"] for x in self.sources[-5:]],
                         ["official_primary"] * 5)
        for source in self.sources:
            self.assertTrue(source["homepage_url"].startswith("https://"))
            self.assertNotIn("@", source["homepage_url"])
            self.assertIn(".", source["publisher_host"])
        self.assertIn("not", self.data["production_rule"].lower())
        self.assertIn("criticism", self.data["verification_rule"])

    def test_query_generation_has_exact_50_source_scoped_non_network_queries(self):
        queries = generate_queries(self.data)
        self.assertEqual(len(queries), 50)
        self.assertEqual([q["priority"] for q in queries], list(range(1, 51)))
        for query in queries:
            self.assertIn("site:", query["query"])
            self.assertIn('"وزارة التخطيط"', query["query"])
            self.assertIn(" OR ", query["query"])
        self.assertEqual(len(generate_queries(self.data, official_only=True)), 5)
        self.assertEqual(len(generate_queries(self.data, limit=7)), 7)
        with self.assertRaises(ValueError):
            generate_queries(self.data, limit=51)
        with self.assertRaises(ValueError):
            build_query({"publisher_host": "bad.com/path"})
        self.assertFalse(any(q["feed_operational"] for q in queries[-5:]))

    def test_research_script_is_offline_not_a_scheduled_sender(self):
        code = (ROOT / "research_source_queries.py").read_text("utf-8")
        for forbidden in ("smtplib", "urllib.request", "requests.get(",
                          "GITHUB_TOKEN", "RASD_GMAIL_APP_PASSWORD", "subprocess"):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
