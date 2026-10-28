"""MA'AL two-stage business reasoning contract — FROZEN before runtime trials.

The model must first establish relevance from authenticated publisher evidence.
Only ACTION_WORTH_REVIEW is eligible to request a separate action contract.
Automated acceptance is a candidate screen, NEVER human editorial signoff.
No existing Gate H decision, review API, or owner state is modified.
"""
from __future__ import annotations
import re
from maal.competition_benchmark_v2 import source_prompt

VERSION="MAAL-TWO-STAGE-FROZEN-V1-20261029"
OUTCOMES=("ACTION_WORTH_REVIEW","MONITOR_ONLY","INSUFFICIENT_EVIDENCE","NOT_RELEVANT","ANALYSIS_HOLD")
NO_ACTION=OUTCOMES[1:]
COMPANY="SYNTHETIC_EGYPT_DIGITAL_STUDIO"
def stage_one_schema(quotes):
    s={"type":"string","minLength":10}
    props={
      "evidence_id":{"type":"string"},
      "company_key":{"type":"string","enum":[COMPANY]},
      "source_url":{"type":"string"},
      "facts":{"type":"array","minItems":1,"maxItems":2,"items":{"type":"string","enum":quotes}},
      "company_fit":{"type":"string","enum":["DIRECT","POSSIBLE","NONE","UNKNOWN"]},
      "causal_reason":s,"business_relevance":s,
      "impact_conditions":{"type":"array","minItems":2,"maxItems":4,"items":s},
      "unknowns":{"type":"array","minItems":2,"maxItems":4,"items":s},
      "alternatives":{"type":"array","minItems":2,"maxItems":3,"items":s},
      "outcome":{"type":"string","enum":list(OUTCOMES)},
      "outcome_reason":s,
      "approved":{"const":False},"executed":{"const":False},"financial_estimate":{"type":"null"}
    }
    return {"type":"object","additionalProperties":False,"properties":props,"required":list(props)}
def stage_two_schema():
    s={"type":"string","minLength":10}
    props={"evidence_id":{"type":"string"},"company_key":{"type":"string","enum":[COMPANY]},
           "stage_one_run_id":{"type":"string"},"title":s,"deliverable":s,
           "priority":{"type":"string","enum":["LOW","MEDIUM"]},
           "priority_reason":s,"owner_role":s,"completion_criteria":s,
           "source_url":{"type":"string"},
           "approved":{"const":False},"executed":{"const":False},
           "external_actions":{"const":False},"financial_estimate":{"type":"null"}}
    return {"type":"object","additionalProperties":False,"properties":props,"required":list(props)}
def _arabic(s):
    return isinstance(s,str) and len(re.findall(r"[\u0600-\u06FF]",s))>=10
def _no_financial_claim(obj):
    if not isinstance(obj,dict):return False
    text=" ".join(str(x) for x in obj.values())
    return not re.search(r"(?i)(?:USD|EGP|EUR|\$)\s*\d|\d[\d,.]*\s*(?:دولار|جنيه|يورو|مليون)\b",text)
def validate_stage_one(case,response):
    schema=stage_one_schema(source_prompt(case)[0])
    if not isinstance(response,dict) or set(response)!=set(schema["properties"]):raise ValueError("stage1_keys")
    if (response.get("evidence_id")!=case["evidence_id"] or
        response.get("source_url")!=case["original_url"] or
        response.get("company_key")!=COMPANY):raise ValueError("stage1_provenance")
    if (response.get("approved") is not False or response.get("executed") is not False or
        response.get("financial_estimate") is not None):raise ValueError("stage1_authority")
    facts=response.get("facts")
    if not isinstance(facts,list) or not 1<=len(facts)<=2 or any(f not in source_prompt(case)[0] for f in facts):
        raise ValueError("stage1_quote_not_from_publisher")
    if response.get("outcome") not in OUTCOMES:raise ValueError("stage1_outcome")
    if response.get("company_fit") not in ("DIRECT","POSSIBLE","NONE","UNKNOWN"):raise ValueError("stage1_company_fit")
    for key in ("impact_conditions","unknowns","alternatives"):
        values=response.get(key)
        if not isinstance(values,list) or not 2<=len(values)<=4 or any(not isinstance(v,str) or len(v)<10 for v in values):
            raise ValueError("stage1_"+key)
    for key in ("causal_reason","business_relevance","outcome_reason"):
        if not _arabic(response.get(key)):raise ValueError("stage1_arabic_"+key)
    if response["outcome"]=="ACTION_WORTH_REVIEW" and response["company_fit"] not in ("DIRECT","POSSIBLE"):
        raise ValueError("action_without_plausible_company_fit")
    if response["company_fit"]=="NONE" and response["outcome"]=="ACTION_WORTH_REVIEW":
        raise ValueError("no_causal_link")
    if not _no_financial_claim(response):raise ValueError("stage1_invented_financial_claim")
    return True
def validate_stage_two(case,response,stage_one,run_id):
    if stage_one["outcome"]!="ACTION_WORTH_REVIEW":raise ValueError("stage2_must_never_run_on_abstention")
    schema=stage_two_schema()
    if not isinstance(response,dict) or set(response)!=set(schema["properties"]):raise ValueError("stage2_keys")
    if (response["evidence_id"]!=case["evidence_id"] or
        response["source_url"]!=case["original_url"] or
        response["company_key"]!=COMPANY or response["stage_one_run_id"]!=run_id):
        raise ValueError("stage2_provenance")
    if (response["approved"] is not False or response["executed"] is not False or
        response["external_actions"] is not False or response["financial_estimate"] is not None):
        raise ValueError("stage2_authority")
    if response["priority"] not in ("LOW","MEDIUM"):raise ValueError("stage2_priority")
    for key in ("title","deliverable","priority_reason","owner_role","completion_criteria"):
        if not _arabic(response.get(key)):raise ValueError("stage2_not_specific_arabic_"+key)
    if len(response["deliverable"])<24 or len(response["completion_criteria"])<24:
        raise ValueError("stage2_not_testable")
    if not _no_financial_claim(response):raise ValueError("stage2_invented_financial_claim")
    return True
def frozen_acceptance(case,s1,s2,error1=None,error2=None):
    """Fixed structural gate. A candidate requires an independent human editorial review."""
    if error1 or not s1:
        return {"status":"HOLD","reason":str(error1 or "missing_stage1"),"critical":True}
    try:validate_stage_one(case,s1)
    except (ValueError,KeyError,TypeError) as exc:
        return {"status":"HOLD","reason":str(exc),"critical":True}
    if s1["outcome"] in NO_ACTION:
        return {"status":"ABSTAIN_VALID","reason":s1["outcome"],"critical":False,
                "action_contradictions":0 if s2 is None else 1}
    if error2 or s2 is None:
        return {"status":"HOLD","reason":str(error2 or "stage2_missing"),"critical":True}
    try:validate_stage_two(case,s2,s1,s2["stage_one_run_id"])
    except (ValueError,KeyError,TypeError) as exc:
        return {"status":"HOLD","reason":str(exc),"critical":True}
    return {"status":"CANDIDATE_FOR_INDEPENDENT_EDITORIAL",
            "reason":"structural_contract_only_not_editorial_pass",
            "critical":False,"action_contradictions":0}
