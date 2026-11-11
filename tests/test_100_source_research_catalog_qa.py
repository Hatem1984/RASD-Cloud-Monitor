"""100-source research is NOT 100 activated feeds. No network or SMTP."""
import json
import unittest
from pathlib import Path
from rasd_hourly_expansion_qa import proposed_catalog_status
ROOT=Path(__file__).resolve().parents[1]
class ResearchCatalogQA(unittest.TestCase):
    def setUp(self):
        self.catalog=json.loads((ROOT/"research_sources_top100_qa.json").read_text("utf-8"))
        self.activated=json.loads((ROOT/"sources_owner_daily_qa.json").read_text("utf-8"))["feeds"]
    def test_exactly_100_unique_candidate_publisher_identities(self):
        self.assertEqual(len(self.catalog["sources"]),100)
        ids=[x["id"] for x in self.catalog["sources"]]
        self.assertEqual(len(set(ids)),100)
        self.assertEqual([x["priority"] for x in self.catalog["sources"]],list(range(1,101)))
    def test_unapproved_50_are_never_scheduled_by_catalog(self):
        fresh=self.catalog["sources"][50:]
        self.assertEqual(len(fresh),50)
        for source in fresh:
            self.assertEqual(source["research_status"],"candidate_not_scheduled")
            self.assertEqual(source["rss_status"],"UNVERIFIED_EXACT_NATIVE_ENDPOINT")
            self.assertEqual(source["original_page_screenshot_status"],"UNVERIFIED")
            self.assertNotIn("feed_url",source)
            self.assertNotIn(source["id"],{x["id"] for x in self.activated})
    def test_active_feeds_stay_13_and_catalog_does_not_expand_private_QA(self):
        self.assertEqual(len(self.activated),13)
        self.assertEqual(self.catalog["production_activated_by_this_file"],0)
        result=proposed_catalog_status(self.activated,self.catalog["sources"])
        self.assertEqual(result["already_researched_distinct_sources"],100)
        self.assertEqual(result["active_approved_native_rss"],13)
        self.assertEqual(result["researched_not_active"],87)
        self.assertIn("HOLD_",result["activation_state"])
    def test_exact_source_endpoint_not_injected_into_approved_runtime(self):
        from monitor import APPROVED_FEED_URLS
        self.assertEqual(len(APPROVED_FEED_URLS),13)
        self.assertEqual({x["url"] for x in self.activated},APPROVED_FEED_URLS)
if __name__=="__main__":unittest.main()
