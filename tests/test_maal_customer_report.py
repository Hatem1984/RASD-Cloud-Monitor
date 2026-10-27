"""MA'AL product recovery acceptance: real-source-labeled historical review, no send."""
import json,unittest
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
H=ROOT/"maal_web"
class CustomerReportContract(unittest.TestCase):
 def setUp(self):
  self.d=json.loads((H/"product_report.json").read_text("utf8"))
 def test_company_and_report_are_explicitly_historical_synthetic(self):
  d=self.d
  self.assertEqual(d["schema"],"MAAL_PRODUCT_REVIEW_V1")
  self.assertEqual(d["mode"],"HISTORICAL_LIMITED_REPORT")
  self.assertIn("افتراضية",d["company"])
  self.assertFalse(d["live_monitoring"])
  self.assertFalse(d["email_sent"])
  self.assertFalse(d["auto_execution"])
 def test_configured_vs_research_catalog_separate(self):
  c=self.d["coverage"]
  self.assertEqual(c["active_feeds_configured"],13)
  self.assertEqual(c["research_catalog"],50)
  self.assertEqual(c["archival_source_count"],3)
  self.assertEqual(c["archival_matching_stories"],1)
  self.assertFalse(c["continuous_coverage_verified"])
 def test_three_source_linked_stories_are_not_fake_approvals(self):
  stories=self.d["stories"]
  self.assertEqual(len(stories),3)
  self.assertEqual([s["published_day"] for s in stories],["2026-10-26","2026-10-24","2026-10-17"])
  for s in stories:
   self.assertFalse(s["ready_for_action"])
   self.assertIn(urlsplit(s["source_url"]).hostname,{"www.mped.gov.eg","mped.gov.eg"})
   for name in ["what_happened","why_it_matters","evidence_status",
                "recommendation","risk","missing","opportunity"]:
    self.assertTrue(s[name])
 def test_different_receipt_tiers_preserved(self):
  levels=[s["evidence_status"] for s in self.d["stories"]]
  self.assertIn("خارجيًا",levels[0])
  self.assertIn("HOLD",levels[1])
  self.assertIn("SHA-256",levels[2])
 def test_all_customer_decisions_are_awaiting_review(self):
  self.assertEqual(len(self.d["decisions"]),3)
  self.assertTrue(all("توصية" in d["approval"] for d in self.d["decisions"]))
 def test_existing_v03_navigation_preserved_with_advanced(self):
  html=(H/"index.html").read_text("utf8")
  for section in ['data-view="overview"','data-view="monitor"',
                  'data-view="report"','data-view="decisions"',
                  'id="view-evidence"','id="view-impact"','id="view-operations"',
                  'id="operator-lab"']:
   self.assertIn(section,html)
  self.assertIn('class="advanced-menu"',html)
  self.assertIn('id="advanced-operator-review"',html)
  self.assertIn('id="customer-answer',html)
if __name__=="__main__":unittest.main()
