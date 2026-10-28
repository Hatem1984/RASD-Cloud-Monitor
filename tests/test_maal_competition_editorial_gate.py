"""General editorial signoff gate and six-step business decision contract tests.

All cases purely synthetic in temporary SQLite fixtures. No owner passwords,
model calls, source downloads, production sends or historical task mutation.
"""
import json,sqlite3,tempfile,unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from maal.competition_benchmark_v2 import validate_contract,rubric,VERSION
from maal.competition_editorial_gate import require_draft_allowed,verified_candidate

class FakeStore:
    def __init__(self,path):self.path=path
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path);db.row_factory=sqlite3.Row
        try:yield db;db.commit()
        finally:db.close()
    def verify_audit(self):return {"integrity":"CHAIN_VERIFIED"}

class FakeGate:
    def __init__(self,store):self.store=store
    def _owner_draft(self,actor,draft_id):
        if actor.get("tenant")!="isolated_owner":raise PermissionError("tenant_restricted")

class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"isolated.sqlite"
        with sqlite3.connect(self.path) as db:
            db.executescript("""
              CREATE TABLE drafts (draft_id TEXT PRIMARY KEY,evidence_id TEXT,
                 evidence_sha256 TEXT,description TEXT);
              CREATE TABLE audit (draft_id TEXT,event TEXT,metadata TEXT,sequence INTEGER);
              INSERT INTO drafts VALUES
                ('old_fpt_draft','source_old','hash_old','bad recommendation'),
                ('new_good_draft','source_verified','hash_verified','Bounded note: one-page competitor review');
              INSERT INTO audit VALUES
                ('old_fpt_draft','DRAFT_CREATED','{"source_model_run_id":"maal-open-deadbeef","evidence_sha256":"hash_old"}',1),
                ('new_good_draft','DRAFT_CREATED','{"source_model_run_id":"maal-paired-12345678901234567890123456789012","evidence_sha256":"hash_verified"}',2);
            """)
        # sqlite3 connection context managers commit but don't close handles
        # on Windows; close explicitly before TemporaryDirectory cleanup.
        db.close()
        self.gateway=FakeGate(FakeStore(self.path))
        self.actor={"tenant":"isolated_owner","login":"test_owner"}

    def test_historical_fpt_cannot_bypass_as_approved_by_old_model(self):
        with self.assertRaises(ValueError):
            require_draft_allowed(self.gateway,self.actor,"old_fpt_draft")
    def test_no_hardcoded_draft_ids_general_new_valid(self):
        with patch("maal.competition_editorial_gate.check_run_binding",
                   return_value=({"evidence_id":"source_verified","evidence_digest":"hash_verified"},
                                 {"rubric_version":VERSION},
                                 "Bounded note: one-page competitor review")):
            result=require_draft_allowed(self.gateway,self.actor,"new_good_draft")
            self.assertEqual(result["evidence_id"],"source_verified")
    def test_unmatched_task_description_rejected(self):
        with patch("maal.competition_editorial_gate.check_run_binding",
                   return_value=({"evidence_id":"source_verified","evidence_digest":"hash_verified"},
                                 {}, "different task")):
            with self.assertRaisesRegex(ValueError,"task_mismatch"):
                require_draft_allowed(self.gateway,self.actor,"new_good_draft")
    def test_tenant_scoped_before_model_review(self):
        with self.assertRaises(PermissionError):
            require_draft_allowed(self.gateway,{"tenant":"other_company"},"new_good_draft")

class ReasoningContractTests(unittest.TestCase):
    def setUp(self):
        self.case={"source_key":"fpt","evidence_id":"e"*24,
            "original_url":"https://itida.gov.eg/official",
            "headline":"FPT Opens Office in Cairo",
            "evidence_digest":"a"*64,
            "source_excerpt":"FPT Opens Office in Cairo. The company is opening a new office in Egypt to serve new clients across several regions."}
        self.a={"evidence_id":self.case["evidence_id"],
          "facts":[self.case["headline"]],
          "business_relevance":{"company_fit":"POSSIBLE",
             "causal_link":"قد تكون صلة منافسة في سوق البرمجيات إذا تشابهت الخدمات",
             "why_company_might_care":"الشركة الافتراضية قد تتأثر إذا كانت خدماتها متداخلة"},
          "impact_conditions":["إذا ثبت تداخل عروض الخدمات بين الطرفين","عند وجود طلب توظيف في تخصصات تتداخل مع فريق الشركة"],
          "alternatives":[
            {"action":"إعداد مذكرة مقارنة","tradeoff":"وقت مراجعة محدود"},
            {"action":"الانتظار إلى تحديث لاحق","tradeoff":"تفويت مبكر للفرص"}],
          "recommendation":{"do_action":True,"why":"بسبب عدم ثبوت التنافس المباشر نبدأ بتحقق صغير",
                            "bounded_internal_step":"إعداد مذكرة مقارنة من صفحة واحدة"},
          "action_contract":{"title":"مراجعة المنافسة","deliverable":"مذكرة صفحة واحدة بثلاثة فروق قابلة للتحقق",
                             "priority":"LOW","owner_role":"مسؤول تحليل السوق",
                             "completion_criteria":"ذكر فروق محددة مع مصدر كل فرق",
                             "evidence_id":self.case["evidence_id"]},
          "unknowns":["لا توجد بيانات عن تداخل الخدمات","لا توجد بيانات عن تعاقدات جديدة"],
          "source_url":self.case["original_url"],"financial_estimate":None,
          "approved":False,"executed":False}
    def test_valid_grounded_contract(self):
        self.assertTrue(validate_contract(self.case,self.a))
        self.assertIn(rubric(self.case,self.a)["status"],("HOLD_SEMANTIC","CANDIDATE_FOR_EDITORIAL"))
    def test_unbound_source_refused(self):
        x={**self.a,"source_url":"https://different.example"}
        with self.assertRaisesRegex(ValueError,"source_bind"):
            validate_contract(self.case,x)
    def test_no_action_must_not_trigger_task(self):
        x={**self.a,"recommendation":{**self.a["recommendation"],"do_action":False}}
        with self.assertRaisesRegex(ValueError,"no_action_must_have_none_priority"):
            validate_contract(self.case,x)
    def test_model_cannot_approve_itself(self):
        x={**self.a,"approved":True}
        with self.assertRaisesRegex(ValueError,"invalid_authority"):
            validate_contract(self.case,x)

if __name__=="__main__":unittest.main()
