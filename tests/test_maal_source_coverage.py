"""Gate C: configuration-only source coverage cannot be mislabeled as live QA."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from maal.source_coverage import source_coverage


ROOT = Path(__file__).resolve().parents[1]


def fixture(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class MaalSourceCoverageAcceptance(unittest.TestCase):
    def setUp(self):
        self.research = fixture("research_sources_top50.json")
        self.active = fixture("sources_newsroom_active.json")
        self.candidates = fixture("sources_newsroom_expansion_candidates.json")

    def audit(self):
        return source_coverage(self.research, self.active, self.candidates)

    def test_latest_reviewed_monitoring_scope_is_not_exaggerated(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
            result = self.audit()
        self.assertEqual(result["research_catalog_count"], 50)
        self.assertEqual(result["active_rss_feed_count"], 13)
        self.assertEqual(result["catalog_not_activated_count"], 37)
        self.assertEqual(result["keyword_count"], 29)
        self.assertEqual(result["candidate_count"], 9)
        self.assertFalse(result["source_page_and_image_live_verified"])
        self.assertFalse(result["gmail_inbox_delivery_verified"])

    def test_new_unreviewed_rss_is_rejected(self):
        candidate = copy.deepcopy(self.active["feeds"][0])
        candidate["id"] = "unapproved_added_feed"
        self.active["feeds"].append(candidate)
        with self.assertRaisesRegex(ValueError, "active_feed_not_in_reviewed_catalog"):
            self.audit()

    def test_non_https_feed_is_not_permitted(self):
        self.active["feeds"][0]["url"] = "http://example.org/rss"
        with self.assertRaisesRegex(ValueError, "active_feed_requires_trusted_https"):
            self.audit()

    def test_candidate_cannot_claim_activation_without_source_approval(self):
        self.candidates["candidates"].append(
            {"id": "unknown_newspaper", "status": "ACTIVATED_WITHOUT_QA"})
        with self.assertRaisesRegex(ValueError, "candidate_claims_activation"):
            self.audit()

    def test_duplicate_keyword_is_not_counted_as_new_coverage(self):
        self.active["keywords"].append(self.active["keywords"][0].upper())
        with self.assertRaisesRegex(ValueError, "duplicate_monitored_keyword"):
            self.audit()

    def test_duplicate_source_id_is_detected(self):
        self.active["feeds"].append(copy.deepcopy(self.active["feeds"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate_active_feed_id"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
