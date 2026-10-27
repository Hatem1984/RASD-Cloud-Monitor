"""MA'AL existing V0.3 historical-only staged-report safety and update contracts."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json,unittest
from maal_web import server
class SnapshotSafety(unittest.TestCase):
 def setUp(self):
  self.temp=TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/"current.json"
  self.data=json.loads((server.HERE/"product_report.json").read_text("utf8"))
  self.meta={"kind":"HISTORICAL_READONLY_QA","revision":"qa-static-abc",
   "source_live_connected":False,
   "source_new_verified_news_count":0,"no_email_sent":True,
   "original_gate_e_sha256":"f"*64}
 def read(self):
  d=dict(self.data)
  d["snapshot_meta"]=dict(self.meta)
  self.path.write_text(json.dumps(d,ensure_ascii=False),encoding="utf8")
  with patch.object(server,"STAGED_REVIEW",self.path),patch.object(
      server,"get_case",return_value={"evidence_digest":"f"*64}):
   return server.get_safe_staging_report()
 def test_safe_staging_metadata_preserves_exact_original_report(self):
  d=self.read()
  self.assertEqual(d["signals"],self.data["signals"])
  self.assertEqual(d["snapshot_meta"]["source_new_verified_news_count"],0)
 def test_forged_fact_rejected(self):
  self.data["signals"][0]["facts"].append("سند مالي مختلق")
  with self.assertRaisesRegex(ValueError,"snapshot_source_changed"):
   self.read()
 def test_live_mode_denied(self):
  self.meta["source_live_connected"]=True
  with self.assertRaisesRegex(ValueError,"unverified_freshness"):
   self.read()
 def test_fake_new_news_denied(self):
  self.meta["source_new_verified_news_count"]=1
  with self.assertRaisesRegex(ValueError,"unverified_freshness"):
   self.read()
 def test_claim_email_sent_denied(self):
  self.meta["no_email_sent"]=False
  with self.assertRaisesRegex(ValueError,"unverified_freshness"):
   self.read()
 def test_wrong_original_evidence_sha_denied(self):
  self.meta["original_gate_e_sha256"]="0"*64
  with self.assertRaisesRegex(ValueError,"gate_e_original_sha256"):
   self.read()
 def test_browser_displays_distinct_qa_refresh_not_live(self):
  js=(server.HERE/"app.js").read_text("utf8")
  html=(server.HERE/"index.html").read_text("utf8")
  self.assertIn("setInterval(pollSafeReview,12000)",js)
  self.assertIn("هذا ليس فحص RSS حيًا",js)
  self.assertIn('id="customer-snapshot-status"',html)
  self.assertIn('MAAL_HISTORICAL_SNAPSHOT_REVIEW', (server.HERE/"server.py").read_text("utf8"))
if __name__=="__main__":unittest.main()
