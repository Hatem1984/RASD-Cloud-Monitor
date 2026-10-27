"""Public CI: synthetic Gate H runtime/archiving tests only; no owner data or model."""
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
import unittest,tempfile,json
from maal import demo_runtime as runtime

class FakeProvider:
 def __init__(self):
  self.model="SYNTHETIC_MOCK_ONLY"
  self.last_elapsed_seconds=3.25
  self.last_usage={"total_tokens":99}

CASE={
 "timeliness":"HISTORICAL","verified_receipt":True,
 "evidence_id":"SYNTHETIC_GATE_H_EVIDENCE",
 "publisher":"Synthetic CI Publisher",
 "original_url":"https://example.org/test-only",
 "finding":"An imaginary announcement discusses infrastructure funding.",
 "published_day":"2026-10-15",
 "observed_at":"2026-10-16T01:00:00+00:00",
 "evidence_digest":"c"*64,
 "verification_status":"VERIFIED_ORIGINAL_PAGE"
}
MODEL_DRAFT={"status":"AI_DRAFT_UNREVIEWED",
 "verified_evidence_ids":[CASE["evidence_id"]],
 "human_approval_required":True,
 "action_executed":False,
 "recommendation_draft":"Synthetic internal review only"}

class RuntimeBoundaryTests(unittest.TestCase):
 def setUp(self):
  runtime.LAST_RUN=0
 def test_fresh_receipt_is_archived_without_permission(self):
  with tempfile.TemporaryDirectory() as temp:
   target=Path(temp)/"fresh_model_run.json"
   with patch.object(runtime,"LocalLlamaCppProvider",FakeProvider),patch.object(runtime,"analyze",return_value=MODEL_DRAFT):
    outcome=runtime.infer_to_local_receipt(CASE,target)
   self.assertTrue(outcome["run_id"].startswith("maal-g3-"))
   raw=json.loads(target.read_text("utf8"))
   self.assertEqual(raw["human_review"],"HOLD")
   self.assertFalse(raw["external_actions_executed"])
   self.assertEqual(raw["run_id"],outcome["run_id"])
   archival=target.parent/"runs"/(raw["run_id"]+".json")
   self.assertEqual(archival.read_bytes(),target.read_bytes())
   self.assertEqual(len(list(archival.parent.iterdir())),1)
 def test_rejects_live_claim_without_verified_contract(self):
  with tempfile.TemporaryDirectory() as temp:
   with self.assertRaisesRegex(ValueError,"expected_historical"):
    runtime.infer_to_local_receipt(dict(CASE,timeliness="LIVE"),Path(temp)/"run.json")
 def test_rejects_parallel_task_before_model(self):
  with tempfile.TemporaryDirectory() as temp:
   runtime.LOCK.acquire()
   try:
    with self.assertRaisesRegex(RuntimeError,"already_running"):
     runtime.infer_to_local_receipt(CASE,Path(temp)/"run.json")
   finally:runtime.LOCK.release()
 def test_cooldown_refuses_replay_after_success(self):
  with tempfile.TemporaryDirectory() as temp:
   target=Path(temp)/"run.json"
   with patch.object(runtime,"LocalLlamaCppProvider",FakeProvider),patch.object(runtime,"analyze",return_value=MODEL_DRAFT):
    runtime.infer_to_local_receipt(CASE,target)
    with self.assertRaisesRegex(RuntimeError,"model_run_cooldown"):
     runtime.infer_to_local_receipt(CASE,target)

if __name__=="__main__":unittest.main()
