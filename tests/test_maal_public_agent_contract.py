"""Public CI: synthetic contract-only fixtures, never owner evidence or live AI."""
from __future__ import annotations
import unittest
from dataclasses import replace
from datetime import datetime,date,timezone
from maal.ai_decision_engine import analyze,CompanyProfile,ALLOWED_DECISION_OPTIONS,ALLOWED_IMPACT_HYPOTHESES,ALLOWED_UNKNOWNS
from maal.decision_contracts import BusinessContext,Evidence

class StubModel:
    def __init__(self,payload):self.payload=payload;self.calls=0
    def propose(self,prompt):self.calls+=1;return self.payload

class PublicContractSafety(unittest.TestCase):
    def setUp(self):
        self.evidence=Evidence(
            evidence_id="SYNTHETIC_PUBLIC_CI_EVIDENCE",
            publisher="CI synthetic publisher only",
            original_url="https://example.org/ci-fixture",
            claim="Synthetic public contract fixture: an infrastructure policy is under discussion.",
            published_at=date(2026,10,1),
            observed_at=datetime(2026,10,2,tzinfo=timezone.utc),
            original_page_sha256="a"*64,
            status="VERIFIED_ORIGINAL_PAGE")
        self.company=CompanyProfile(
            BusinessContext("SYNTHETIC_CI_ACCOUNT","infrastructure","Egypt"),
            objective="Follow official policy changes",relevant_sectors=("energy","construction"))
        self.answer={
            "evidence_ids":[self.evidence.evidence_id],
            "relevant_to_company":True,
            "facts":[self.evidence.claim],
            "hypothesis":ALLOWED_IMPACT_HYPOTHESES[0],
            "unknowns":[ALLOWED_UNKNOWNS[0]],
            "alternatives":[ALLOWED_DECISION_OPTIONS[0],ALLOWED_DECISION_OPTIONS[1]],
            "recommendation":ALLOWED_DECISION_OPTIONS[1],
            "verify_with":"await_human_review","financial_estimate":None,
            "executed":False,"approved":False}
    def test_valid_contract_is_unreviewed_not_executed(self):
        p=StubModel(self.answer);r=analyze(self.company,(self.evidence,),p)
        self.assertEqual(r["status"],"AI_DRAFT_UNREVIEWED")
        self.assertFalse(r["action_executed"])
        self.assertEqual(p.calls,1)
    def test_unverified_source_prevents_model_invocation(self):
        p=StubModel(self.answer)
        with self.assertRaisesRegex(ValueError,"unverified_evidence"):
            analyze(self.company,(replace(self.evidence,status="SOURCE_CONFLICT"),),p)
        self.assertEqual(p.calls,0)
    def test_no_unverified_evidence_ids(self):
        a=dict(self.answer,evidence_ids=["WRONG_ID"])
        with self.assertRaisesRegex(ValueError,"model_cited_unverified_evidence"):
            analyze(self.company,(self.evidence,),StubModel(a))
    def test_malformed_facts_object_is_rejected_without_typeerror(self):
        a=dict(self.answer,facts=[{"claim":"malformed"}])
        with self.assertRaisesRegex(ValueError,"model_invented_factual_claim"):
            analyze(self.company,(self.evidence,),StubModel(a))
    def test_duplicate_alternatives_are_rejected(self):
        a=dict(self.answer,alternatives=["Wait","Wait"])
        with self.assertRaisesRegex(ValueError,"alternatives_not_distinct"):
            analyze(self.company,(self.evidence,),StubModel(a))
    def test_fake_ai_execution_is_rejected(self):
        for flag in ("executed","approved"):
            with self.subTest(flag=flag):
                a=dict(self.answer);a[flag]=True
                with self.assertRaisesRegex(ValueError,"exceed_authority"):
                    analyze(self.company,(self.evidence,),StubModel(a))
    def test_unsupported_financial_claim_rejected(self):
        a=dict(self.answer,financial_estimate=1000000)
        with self.assertRaisesRegex(ValueError,"exceed_authority"):
            analyze(self.company,(self.evidence,),StubModel(a))
    def test_synthetic_fixture_is_not_independently_verified(self):
        # This fixture validates schema only; it is not an official RASD proof.
        self.assertEqual(self.evidence.publisher,"CI synthetic publisher only")
        self.assertEqual(self.evidence.original_page_sha256,"a"*64)
if __name__=="__main__":unittest.main()
