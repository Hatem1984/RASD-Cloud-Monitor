"""Gate G3 contract tests; fake provider tests safety only, never counted as real AI inference."""
import unittest
from pathlib import Path as _Path
import os as _os
_OWNER_PROOF = _os.name == "nt" and _Path(
    r"E:\MAAL\03_REPORTS_AND_REVIEW\MAAL_GATE_E_ACCEPTANCE_20261026\MAAL-historical-signal-demo.json"
).is_file()
from dataclasses import replace
from datetime import date, datetime
from maal.ai_decision_engine import analyze,CompanyProfile
from maal.decision_contracts import BusinessContext,Evidence


class FakeProvider:
    def __init__(self, reply):
        self.reply=reply
        self.called=False
    def propose(self,prompt):
        self.called=True
        return self.reply

@unittest.skipUnless(_OWNER_PROOF, "Owner-only E evidence needed; no fabricated CI provenance")
class G3Tests(unittest.TestCase):
    def setUp(self):
        from maal_web.server import get_case
        case=get_case()
        self.evidence=Evidence(
            evidence_id=case["evidence_id"],publisher=case["publisher"],
            original_url=case["original_url"],claim=case["finding"],
            published_at=date.fromisoformat(case["published_day"]),
            observed_at=datetime.fromisoformat(case["observed_at"]),
            original_page_sha256=case["evidence_digest"],
            status=case["verification_status"])
        self.profile=CompanyProfile(
            BusinessContext("SYNTHETIC_EGYPT_INFRA","بنية تحتية وطاقة متجددة","مصر"),
            "فهم المخاطر والفرص دون التزامات مالية",
            ("infrastructure_finance","renewable_energy"))
        self.answer={
            "evidence_ids":[self.evidence.evidence_id],"relevant_to_company":True,
            "facts":[self.evidence.claim],
            "hypothesis":"ربما تستدعي هذه المناقشات متابعة القرارات الرسمية قبل التخطيط",
            "unknowns":["لا توجد شروط أهلية منشورة مثبتة من الدليل الحالي"],
            "alternatives":["المتابعة","عدم اتخاذ إجراء حتى صدور شروط رسمية"],
            "recommendation":"أعد ملف مراجعة داخلي دون إرسال أو تنفيذ",
            "verify_with":"official_publisher_original",
            "financial_estimate":None,"executed":False,"approved":False
        }

    def test_structured_draft_is_non_executable(self):
        data=analyze(self.profile,(self.evidence,),FakeProvider(self.answer))
        self.assertEqual(data["status"],"AI_DRAFT_UNREVIEWED")
        self.assertFalse(data["action_executed"])
        self.assertTrue(data["model_output_requires_factual_human_review"])

    def test_invalid_evidence_blocks_model_call(self):
        model=FakeProvider(self.answer)
        with self.assertRaises(ValueError):
            analyze(self.profile,(replace(self.evidence,status="HOLD"),),model)
        self.assertFalse(model.called)

    def test_model_invented_id_rejected(self):
        answer={**self.answer,"evidence_ids":["fake-proof-999"]}
        with self.assertRaisesRegex(ValueError,"model_cited_unverified"):
            analyze(self.profile,(self.evidence,),FakeProvider(answer))

    def test_unquoted_claim_rejected(self):
        answer={**self.answer,"facts":["صدر قرار بتمويل جميع الشركات"]}
        with self.assertRaisesRegex(ValueError,"model_invented_factual_claim"):
            analyze(self.profile,(self.evidence,),FakeProvider(answer))

    def test_model_cannot_authorize_or_execute(self):
        for key in ("approved","executed"):
            with self.subTest(key=key):
                answer={**self.answer,key:True}
                with self.assertRaisesRegex(ValueError,"exceed_authority"):
                    analyze(self.profile,(self.evidence,),FakeProvider(answer))

    def test_model_cannot_estimate_money(self):
        answer={**self.answer,"financial_estimate":1000000}
        with self.assertRaisesRegex(ValueError,"exceed_authority"):
            analyze(self.profile,(self.evidence,),FakeProvider(answer))

    def test_no_assessment_without_uncertainty(self):
        answer={**self.answer,"unknowns":[]}
        with self.assertRaisesRegex(ValueError,"missing_ai_uncertainty"):
            analyze(self.profile,(self.evidence,),FakeProvider(answer))

    def test_real_customer_without_authorized_baseline_rejected(self):
        with self.assertRaisesRegex(ValueError,"real_client_analysis_requires_authorization"):
            analyze(replace(self.profile,synthetic=False),
                    (self.evidence,),FakeProvider(self.answer))
if __name__=="__main__":
    unittest.main()
