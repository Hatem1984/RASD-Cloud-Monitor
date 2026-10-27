"""OS-independent synthetic contracts from the exact original V0.3 function AST.

Do not import the complete owner-local web server in Linux CI; its explicit
MAAL owner root safety gate is intentional, and must remain unchanged.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import ast,json,unittest
HERE=Path(__file__).resolve().parents[1]/"maal_web"
raw=(HERE/"server.py").read_text("utf8")
tree=ast.parse(raw)
matches=[node for node in tree.body if isinstance(node,ast.FunctionDef)
         and node.name=="get_safe_staging_report"]
assert len(matches)==1
EXACT_FUNC=compile(ast.Module(body=matches,type_ignores=[]),
                   str(HERE/"server.py"),"exec")
class SnapshotSafety(unittest.TestCase):
 def setUp(self):
  self.temp=TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/"current.json"
  self.data=json.loads((HERE/"product_report.json").read_text("utf8"))
  self.meta={"kind":"HISTORICAL_READONLY_QA","revision":"qa-static-abc",
   "source_live_connected":False,
   "source_new_verified_news_count":0,"no_email_sent":True,
   "original_gate_e_sha256":"f"*64}
 def read(self):
  d=dict(self.data)
  d["snapshot_meta"]=dict(self.meta)
  self.path.write_text(json.dumps(d,ensure_ascii=False),encoding="utf8")
  namespace={"json":json,"HERE":HERE,"STAGED_REVIEW":self.path,
             "get_case":lambda:{"evidence_digest":"f"*64}}
  exec(EXACT_FUNC,namespace)
  return namespace["get_safe_staging_report"]()
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
  js=(HERE/"app.js").read_text("utf8")
  html=(HERE/"index.html").read_text("utf8")
  self.assertIn("setInterval(pollSafeReview,12000)",js)
  self.assertIn("هذا ليس فحص RSS حيًا",js)
  self.assertIn('id="customer-snapshot-status"',html)
  self.assertIn('MAAL_HISTORICAL_SNAPSHOT_REVIEW',raw)
if __name__=="__main__":unittest.main()
