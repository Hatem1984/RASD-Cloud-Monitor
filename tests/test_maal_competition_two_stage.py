"""Frozen two-stage safety contract tests. Synthetic data only; no network."""
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from maal.competition_two_stage_contract import (
 stage_one_schema,stage_two_schema,validate_stage_one,validate_stage_two,frozen_acceptance)
from maal.competition_benchmark_v2 import source_prompt

class TwoStageSafetyTests(unittest.TestCase):
 def setUp(self):
  self.case={"source_key":"fpt","evidence_id":"proof-01","original_url":"https://example.org/verified",
   "headline":"FPT Opens Office in Cairo, Expanding Global Delivery Network",
   "source_excerpt":"FPT Opens Office in Cairo, Expanding Global Delivery Network. A company announced an office in Cairo with formal context."}
  facts=source_prompt(self.case)[0]
  self.s1={"evidence_id":"proof-01","company_key":"SYNTHETIC_EGYPT_DIGITAL_STUDIO",
   "source_url":self.case["original_url"],"facts":[facts[0]],
   "company_fit":"POSSIBLE",
   "causal_reason":"قد يؤثر وجود فريق جديد على عرض مهارات التوظيف في السوق إذا تنافس على نفس العملاء.",
   "business_relevance":"تهتم الشركة الافتراضية بدراسة السوق بشرط التحقق من نطاق التخصص.",
   "impact_conditions":["إذا استهدف الفريق مهارات مماثلة لأعمال الشركة الصغيرة.",
                         "إذا توفرت معلومات منشورة تقارن الطلب على المهارات."],
   "unknowns":["مدى توافق خدمات الفرع مع خدمات الشركة الحالية",
               "هل يوجد تنافس على نفس شريحة العملاء أم لا"],
   "alternatives":["متابعة المصدر بانتظام دون تغيير أعمال الشركة",
                   "دراسة مهارات الفرع والخدمات بمذكرة داخلية"],
   "outcome":"ACTION_WORTH_REVIEW",
   "outcome_reason":"قد تكون مذكرة داخلية محددة مفيدة قبل أي قرار عن التوسع.",
   "approved":False,"executed":False,"financial_estimate":None}
  self.s2={"evidence_id":"proof-01","company_key":"SYNTHETIC_EGYPT_DIGITAL_STUDIO",
   "stage_one_run_id":"maal-two-stage-123",
   "title":"إعداد مذكرة داخلية لمقارنة الخدمات الرقمية",
   "deliverable":"صفحة مقارنة بأهم خدمتين متشابهتين بين أنشطة الشركة ونشاط الناشر المنشور.",
   "priority":"LOW",
   "priority_reason":"لأن الصلة احتمالية ولا توجد معلومات تثبت علاقة مباشرة أو أثرًا ماليًا.",
   "owner_role":"مسؤول بحوث السوق في الفريق الافتراضي",
   "completion_criteria":"تتضمن المذكرة مصدرين أصليين وأسئلة معلقة وثلاث ملاحظات قابلة للتدقيق.",
   "source_url":self.case["original_url"],"approved":False,"executed":False,
   "external_actions":False,"financial_estimate":None}
 def test_contract_freeze(self):
  self.assertIn("ACTION_WORTH_REVIEW",stage_one_schema(source_prompt(self.case)[0])["properties"]["outcome"]["enum"])
  self.assertNotIn("priority",stage_one_schema(source_prompt(self.case)[0])["properties"])
  self.assertNotIn("NONE",stage_two_schema()["properties"]["priority"]["enum"])
 def test_valid_candidate_is_not_approval(self):
  self.assertTrue(validate_stage_one(self.case,self.s1))
  self.assertTrue(validate_stage_two(self.case,self.s2,self.s1,"maal-two-stage-123"))
  self.assertEqual(frozen_acceptance(self.case,self.s1,self.s2,expected_stage_one_run_id="maal-two-stage-123")["status"],"CANDIDATE_FOR_INDEPENDENT_EDITORIAL")
 def test_abstain_never_calls_stage_two(self):
  x={**self.s1,"outcome":"MONITOR_ONLY","company_fit":"UNKNOWN"}
  self.assertEqual(frozen_acceptance(self.case,x,None)["status"],"ABSTAIN_VALID")
  self.assertRaises(ValueError,validate_stage_two,self.case,self.s2,x,"maal-two-stage-123")
  self.assertEqual(frozen_acceptance(self.case,x,self.s2)["action_contradictions"],1)
 def test_approval_gate_needs_actual_stage1_binding(self):
  self.assertEqual(frozen_acceptance(self.case,self.s1,self.s2)["status"],"HOLD")
  self.assertEqual(frozen_acceptance(self.case,self.s1,self.s2,
                  expected_stage_one_run_id="wrong")["status"],"HOLD")
 def test_unfounded_action_blocked(self):
  x={**self.s1,"company_fit":"NONE"}
  self.assertRaises(ValueError,validate_stage_one,self.case,x)
 def test_wrong_evidence_blocked(self):
  x={**self.s1,"evidence_id":"different"}
  self.assertRaises(ValueError,validate_stage_one,self.case,x)
 def test_fake_fact_blocked(self):
  x={**self.s1,"facts":["fabricated partnership confirmed"]}
  self.assertRaises(ValueError,validate_stage_one,self.case,x)
 def test_stage_two_binding_blocked(self):
  x={**self.s2,"stage_one_run_id":"wrong"}
  self.assertRaises(ValueError,validate_stage_two,self.case,x,self.s1,"maal-two-stage-123")
 def test_stage_two_external_action_blocked(self):
  x={**self.s2,"external_actions":True}
  self.assertRaises(ValueError,validate_stage_two,self.case,x,self.s1,"maal-two-stage-123")
 def test_stage_two_financial_claim_blocked(self):
  x={**self.s2,"deliverable":"تحقيق ربح قدره 1000 دولار من التعاقد مع الشركة"}
  self.assertRaises(ValueError,validate_stage_two,self.case,x,self.s1,"maal-two-stage-123")
 def test_runtime_abstention_does_not_call_action_model(self):
  from maal.competition_two_stage_run import run_case
  case={**self.case,"published_day":"2026-10-14",
        "evidence_digest":"a"*64}
  abstain={**self.s1,"outcome":"MONITOR_ONLY","company_fit":"UNKNOWN"}
  first={"output":abstain,"raw":{},"error":None,"seconds":1.0,
         "memory_mb":None,"model_usage":{},"request_sha256":"a","raw_response_sha256":"b"}
  with TemporaryDirectory() as scratch:
   with patch("maal.competition_two_stage_run.ROOT",Path(scratch)):
    with patch("maal.competition_two_stage_run.call",return_value=first) as mocked:
     receipt=run_case(case)
   self.assertEqual(mocked.call_count,1)
   self.assertFalse(receipt["stage2_called"])
   self.assertEqual(receipt["quality"]["status"],"ABSTAIN_VALID")
   self.assertEqual(list(Path(scratch).glob("*/stage2.json")),[])
 def test_runtime_action_invokes_separate_stage_once(self):
  from maal.competition_two_stage_run import run_case
  case={**self.case,"published_day":"2026-10-14","evidence_digest":"a"*64}
  def fake_call(payload,validator):
   if payload["response_format"]["json_schema"]["name"]=="maal_stage1_evidence_relevance":
    return {"output":self.s1,"raw":{},"error":None,"seconds":1.0,
            "memory_mb":None,"model_usage":{},"request_sha256":"a","raw_response_sha256":"b"}
   run_id=payload["messages"][1]["content"].split('"stage_one_run_id": "')[1].split('"')[0]
   return {"output":{**self.s2,"stage_one_run_id":run_id},"raw":{},"error":None,
           "seconds":2.0,"memory_mb":None,"model_usage":{},
           "request_sha256":"c","raw_response_sha256":"d"}
  with TemporaryDirectory() as scratch:
   with patch("maal.competition_two_stage_run.ROOT",Path(scratch)):
    with patch("maal.competition_two_stage_run.call",side_effect=fake_call) as mocked:
     receipt=run_case(case)
   self.assertEqual(mocked.call_count,2)
   self.assertTrue(receipt["stage2_called"])
   self.assertEqual(receipt["quality"]["status"],"CANDIDATE_FOR_INDEPENDENT_EDITORIAL")
   self.assertFalse(receipt["can_create_owner_draft"])
 def test_no_model_output_holds(self):
  self.assertEqual(frozen_acceptance(self.case,None,None,"timeout")["status"],"HOLD")
if __name__=="__main__":unittest.main()
