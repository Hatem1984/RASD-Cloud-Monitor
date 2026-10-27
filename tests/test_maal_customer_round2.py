"""Round2 unit acceptance: 2 dedup signals, 3 document proofs, no fake live claims."""
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/"maal_web"/"product_report.json").read_text("utf8"))
class CustomerRound2(unittest.TestCase):
 def test_two_signals_without_creating_news(self):
  self.assertEqual(DATA["signal_count"],2)
  self.assertEqual(len(DATA["signals"]),2)
  self.assertEqual(len(DATA["stories"]),3)
  self.assertEqual(DATA["signals"][0]["priority"],"HIGH")
  self.assertEqual(DATA["signals"][1]["priority"],"LOW")
  self.assertEqual(set.union(*(set(x["source_ids"]) for x in DATA["signals"])),
                   {x["id"] for x in DATA["stories"]})
 def test_no_production_claim(self):
  self.assertFalse(DATA["live_monitoring"])
  self.assertFalse(DATA["auto_execution"])
  self.assertFalse(DATA["email_sent"])
  self.assertFalse(DATA["coverage"]["continuous_coverage_verified"])
  self.assertEqual(DATA["coverage"]["active_feeds_configured"],13)
  self.assertEqual(DATA["coverage"]["research_catalog"],50)
 def test_source_provenance_tiers_remain(self):
  tiers={x["id"]:x["verification"] for x in DATA["stories"]}
  self.assertEqual(tiers["ministry_2026_10_17"],"ORIGINAL_VERIFIED")
  self.assertEqual(tiers["ministry_2026_10_24"],"ARCHIVED_HEADLINE_ONLY")
  self.assertEqual(tiers["ministry_2026_10_26"],"OFFICIAL_TEXT_ONLY")
 def test_decisions_owner_timing_are_suggested_never_executed(self):
  for item in DATA["decisions"]:
   self.assertIn("مقترح",item["owner"])
   self.assertTrue(item["follow_up"])
   self.assertIn("غير مُنفذ",item["approval"])
   self.assertTrue(item["evidence_signal_ids"])
 def test_executable_buttons_absent_customer_area(self):
  html=(ROOT/"maal_web"/"index.html").read_text("utf8")
  self.assertIn('id="filter-priority"',html)
  self.assertIn('id="filter-sector"',html)
  self.assertIn('id="filter-verification"',html)
  self.assertIn('id="advanced-operator-review"',html)
  self.assertIn('download hidden>تنزيل التقرير PDF',html)
  self.assertIn('download hidden>تنزيل Word',html)
 def test_offline_model_not_invoked_by_public_report(self):
  js=(ROOT/"maal_web"/"app.js").read_text("utf8")
  self.assertIn('customerSignals.rows',js)
  self.assertIn('eligible_for_execution!==false',js)
  self.assertIn('renderCustomerSignals()',js)
  self.assertIn('"HISTORICAL_LIMITED_REPORT"',js)
 def test_existing_pipeline_uses_original_pr135_module_not_reimplementation(self):
  script=(ROOT/"maal_r2_component_report.py").read_text("utf8")
  self.assertIn("from editorial_quality import build_editorial_brief",script)
  self.assertIn("from daily_report import render_docx",script)
  self.assertIn("from maal.decision_contracts import Evidence,BusinessContext",script)
  self.assertIn('editorial_mode="qa_only"',script)
if __name__=="__main__": unittest.main()
