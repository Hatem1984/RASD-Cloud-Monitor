"""Competition MVP: single verified source/Qwen/run/owner audit linkage, no SMTP."""
import unittest
from maal.competition_journey import assemble_agent_journey


class UnifiedAgentJourney(unittest.TestCase):
    def setUp(self):
        self.case = {
            "evidence_id":"5eb7494a551cdb399031d2c9",
            "verification_status":"VERIFIED_ORIGINAL_PAGE",
            "verified_receipt":True, "timeliness":"HISTORICAL",
            "evidence_digest":"a"*64,
            "publisher":"Official ministry", "headline":"Historical official signal",
            "published_day":"2026-10-17", "observed_at":"2026-10-26T15:00:09+00:00",
            "original_url":"https://mped.gov.eg/singlenews?id=7269&lang=ar"
        }
        self.ai = {
            "source_id":self.case["evidence_id"],"source_sha256":self.case["evidence_digest"],
            "source_url":self.case["original_url"],
            "quality_approval":"HOLD_HUMAN_REVIEW","actions_executed":False,
            "status":"AI_DRAFT_UNREVIEWED","run_id":"maal-g3-0123456789",
            "recorded_at":"2026-10-27T16:00:00+00:00",
            "model":"Qwen3-1.7B-Q4_K_M","inference_seconds":13.4,
            "facts":["Historical fact"],"inference":"Conditional business implication",
            "unknowns":["No eligibility evidence"],"alternatives":["Monitor","Prepare"],
            "recommendation":"Prepare internal review"
        }

    def test_guest_has_no_owner_approval_or_fake_work(self):
        result=assemble_agent_journey(self.case,self.ai)
        self.assertFalse(result["live_signal"])
        self.assertFalse(result["approval"]["authenticated"])
        self.assertEqual(result["approval"]["drafts"],[])
        self.assertFalse(result["operations"]["external_actions"])
        self.assertFalse(result["report"]["ai_run_bound_word_pdf_available"])
        self.assertEqual(result["ai"]["human_review"],"NOT_APPROVED_BY_MODEL")

    def test_owner_draft_is_linked_without_auto_approval(self):
        owner={"role":"OWNER","production":False,"audit_integrity":"CHAIN_VERIFIED",
               "drafts":[{"draft_id":"425b5640-c656-4838-98dc-f2ee477f74da",
                         "state":"DRAFT","description":"Prepare internal review",
                         "evidence_id":self.case["evidence_id"],
                         "approved_by":None,"task_id":None}]}
        r=assemble_agent_journey(self.case,self.ai,owner)
        self.assertTrue(r["approval"]["authenticated"])
        self.assertEqual(r["approval"]["drafts"][0]["state"],"DRAFT")
        self.assertIsNone(r["approval"]["drafts"][0]["task_id"])
        self.assertTrue(r["approval"]["drafts"][0]["matches_current_recommendation"])

    def test_model_evidence_or_digest_mismatch_fails_closed(self):
        for key,bad in (("source_id","other"),("source_sha256","b"*64),
                        ("source_url","https://example.org"),("status","APPROVED"),
                        ("quality_approval","ACCEPTED"),("actions_executed",True)):
            with self.subTest(key=key):
                ai=dict(self.ai);ai[key]=bad
                with self.assertRaises(ValueError):
                    assemble_agent_journey(self.case,ai)

    def test_proof_not_verified_holds(self):
        for key,value in (("verified_receipt",False),
                          ("verification_status","EVIDENCE_HOLD"),
                          ("timeliness","LIVE"),("evidence_digest","bad")):
            with self.subTest(key=key):
                case=dict(self.case);case[key]=value
                with self.assertRaises(ValueError):
                    assemble_agent_journey(case,self.ai)

    def test_broken_audit_and_cross_tenant_blocked(self):
        owner={"role":"OWNER","production":False,"audit_integrity":"BROKEN","drafts":[]}
        with self.assertRaises(ValueError):
            assemble_agent_journey(self.case,self.ai,owner)
        owner["audit_integrity"]="CHAIN_VERIFIED"
        owner["production"]=True
        with self.assertRaises(ValueError):
            assemble_agent_journey(self.case,self.ai,owner)

    def test_unrelated_drafts_cannot_be_misrepresented(self):
        owner={"role":"OWNER","production":False,"audit_integrity":"CHAIN_VERIFIED",
               "drafts":[{"draft_id":"wrong","state":"EXECUTED",
                          "evidence_id":"some-other-source","task_id":"task-0"}]}
        r=assemble_agent_journey(self.case,self.ai,owner)
        self.assertEqual(r["approval"]["drafts"],[])

    def test_future_receipt_is_not_claimed_as_real(self):
        ai=dict(self.ai);ai["recorded_at"]="2099-01-01T00:00:00+00:00"
        with self.assertRaises(ValueError):
            assemble_agent_journey(self.case,ai)


if __name__=="__main__":
    unittest.main()
