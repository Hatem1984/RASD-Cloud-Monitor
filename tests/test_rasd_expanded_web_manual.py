"""Extended manual web research only: 50 origins, zero feed activation."""
import json
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from research_source_queries import load_registry
from rasd_expanded_web_manual import research_search_url


class ExpandedWebManualTests(unittest.TestCase):
    def test_50_source_registry_not_50_production_feeds(self):
        catalog = load_registry()
        active = [s for s in catalog["sources"]
                  if s["research_status"] == "active_native_rss"]
        self.assertEqual(len(catalog["sources"]), 50)
        self.assertEqual(len(active), 13)
        self.assertEqual(len(catalog["sources"]) - len(active), 37)

    def test_user_search_is_manual_and_scoped_to_exact_registered_source(self):
        catalog = load_registry()
        terms = json.loads(Path("sources_newsroom_active.json").read_text(
            encoding="utf-8"))["keywords"]
        source = catalog["sources"][1]
        url = research_search_url(source["id"], terms[0],
                                  registry=catalog, keywords=terms)
        split = urlsplit(url)
        self.assertEqual(split.scheme, "https")
        self.assertEqual(split.hostname, "www.google.com")
        self.assertEqual(parse_qs(split.query)["q"], [
            f'site:{source["publisher_host"]} "{terms[0]}"'
        ])
        with self.assertRaises(ValueError):
            research_search_url("unapproved-source", terms[0],
                                registry=catalog, keywords=terms)
        with self.assertRaises(ValueError):
            research_search_url(source["id"], "private-token-query",
                                registry=catalog, keywords=terms)

    def test_no_modifications_to_production_feed_registry(self):
        path = Path("sources_newsroom_active.json")
        production = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(production["feeds"]), 13)
        self.assertTrue(all(entry["url"].startswith("https://")
                            for entry in production["feeds"]))


if __name__ == "__main__":
    unittest.main()
