"""100-source RESEARCH catalog validation; do not confuse with live RSS count."""
import json
import tempfile
import unittest
from pathlib import Path

from research_source_queries_100 import (
    EXTENSION, load_100_sources, generate_100_queries,
)

ROOT = Path(__file__).resolve().parents[1]


class HundredSourceResearchCatalogTests(unittest.TestCase):
    def test_exact_100_without_changing_original_fifty(self):
        data = load_100_sources()
        self.assertEqual(data["total_research_origins"], 100)
        self.assertEqual(len(data["sources"]), 100)
        self.assertEqual([r["priority"] for r in data["sources"]],
                         list(range(1, 101)))
        first = json.loads((ROOT/"research_sources_top50.json").read_text("utf-8"))
        self.assertEqual(first["sources"], data["sources"][:50])
        self.assertEqual(len({r["publisher_host"] for r in data["sources"]}), 100)

    def test_only_13_are_active_not_one_hundred(self):
        data = load_100_sources()
        self.assertEqual(data["approved_automated_rss_sources"], 13)
        self.assertEqual(data["not_scheduled_research_candidates"], 87)
        self.assertEqual(sum(r["research_status"]=="active_native_rss"
                             for r in data["sources"]),13)
        for row in data["sources"][50:]:
            self.assertEqual(row["rss_status"], "not_verified_no_feed_approved")
            self.assertEqual(row["original_article_screenshot_status"], "not_verified")
            self.assertIsNone(row["last_individual_live_check"])
        active = json.loads((ROOT/"sources_newsroom_active.json").read_text("utf-8"))
        self.assertEqual(len(active["feeds"]),13)

    def test_owner_reference_publishers_are_prioritized(self):
        sources = {r["id"]:r for r in load_100_sources()["sources"]}
        self.assertEqual(sources["soutalomma"]["homepage_url"],
                         "https://www.soutalomma.com/")
        self.assertEqual(sources["daralmaref"]["homepage_url"],
                         "https://daralmaref.com/")
        self.assertEqual(sources["forbesmiddleeast"]["homepage_url"],
                         "https://www.forbesmiddleeast.com/ar/")

    def test_100_source_scoped_queries_not_100_original_rss_claims(self):
        queries = generate_100_queries(load_100_sources())
        self.assertEqual(len(queries),100)
        self.assertEqual(sum(r["approved_automated_source"] for r in queries),13)
        self.assertEqual(len({r["priority"] for r in queries}),100)
        self.assertTrue(all('site:' in r["query"] and
                            '"وزارة التخطيط"' in r["query"] for r in queries))
        self.assertGreaterEqual(len(generate_100_queries(
            load_100_sources(),official_only=True)), 10)
        with self.assertRaises(ValueError):
            generate_100_queries(load_100_sources(),limit=101)

    def test_tampered_candidate_cannot_silently_become_approved(self):
        raw=json.loads(EXTENSION.read_text("utf-8"))
        raw["sources"][0]["research_status"]="active_native_rss"
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/"tampered.json"
            bad.write_text(json.dumps(raw,ensure_ascii=False),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"autoactivation"):
                load_100_sources(bad)

    def test_invalid_host_and_duplicated_ids_fail_closed(self):
        for kind in ("dup_id","unsafe_host"):
            raw=json.loads(EXTENSION.read_text("utf-8"))
            if kind == "dup_id":
                raw["sources"][0]["id"]=raw["sources"][1]["id"]
            else:
                raw["sources"][0]["publisher_host"]="bad.com/path"
            with tempfile.TemporaryDirectory() as td:
                bad=Path(td)/"broken.json"
                bad.write_text(json.dumps(raw,ensure_ascii=False),encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_100_sources(bad)


if __name__ == "__main__":
    unittest.main()
