"""General, source-and-model-bound editorial signoff required by owner actions.

Separate from model grading. Owner verifies editorial quality with a second
password entry. A local SQLite immutable attestation pins evidence, model,
answer hash, rubric and bounded task description. AI cannot issue a signoff.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime,timezone

from maal.competition_new_source import ROOT as SOURCE_ROOT,get_case_from_capture
from maal.competition_benchmark_v2 import VERSION,validate_contract,rubric
from maal.competition_run_paired import ROOT as BENCH_ROOT

def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,
                                      separators=(",",":")).encode("utf8")).hexdigest()
def verified_candidate(run_id):
    if not isinstance(run_id,str) or not re.fullmatch(r"maal-paired-[0-9a-f]{32}",run_id):
        raise ValueError("new_independent_model_run_required")
    file=BENCH_ROOT/run_id/"receipt.json"
    candidate=json.loads(file.read_text("utf8"))
    if candidate.get("run_id")!=run_id or candidate.get("rubric_version")!=VERSION:
        raise ValueError("model_run_or_rubric_changed")
    case_path=SOURCE_ROOT/candidate["source_id"]
    case=get_case_from_capture(case_path)
    if (candidate["source_sha256"]!=case["evidence_digest"] or
         candidate["case_url"]!=case["original_url"] or
         candidate["company_key"]!="SYNTHETIC_EGYPT_DIGITAL_STUDIO"):
        raise ValueError("model_evidence_company_mismatch")
    answer=candidate.get("response_json")
    validate_contract(case,answer)
    grade=rubric(case,answer)
    if grade["status"]!="CANDIDATE_FOR_EDITORIAL":
        raise ValueError("weak_model_result_hold")
    if candidate.get("grade")!=grade:
        raise ValueError("model_grade_no_longer_matches_frozen_rubric")
    if answer["recommendation"]["do_action"] is not True:
        raise ValueError("no_recommendation_no_task")
    # These extra release guards do not alter frozen benchmark scoring.
    # An English-only answer or a task with no causal business fit cannot be
    # treated as an Arabic owner-reviewable actionable decision.
    narrative=json.dumps({
       k:answer[k] for k in ("business_relevance","impact_conditions",
          "alternatives","recommendation","action_contract","unknowns")
    },ensure_ascii=False)
    if len(re.findall(r"[\u0600-\u06FF]",narrative))<35:
        raise ValueError("arabic_business_decision_not_established")
    if (answer["business_relevance"]["company_fit"]=="NONE" and
        answer["recommendation"]["do_action"] is True):
        raise ValueError("no_causal_business_fit_for_action")
    if re.search(r"(?i)(?:USD|EGP|EUR|\$)\s*\d|\d[\d,.]*\s*(?:دولار|جنيه|يورو|مليون)\b",
                 narrative):
        raise ValueError("unverified_financial_numbers_in_business_decision")
    contract=answer["action_contract"]
    title=contract["title"].strip()
    deliverable=contract["deliverable"].strip()
    if not 5<=len(title)<=160 or not 12<=len(deliverable)<=210:
        raise ValueError("impractical_task_contract")
    description=f"{title}: {deliverable}"
    if len(description)>500:raise ValueError("task_too_large")
    return case,candidate,grade,description

def ensure_tables(store):
    with store.db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS editorial_signoffs(
          model_run_id TEXT PRIMARY KEY,
          evidence_id TEXT NOT NULL,
          evidence_sha256 TEXT NOT NULL,
          result_sha256 TEXT NOT NULL,
          rubric_version TEXT NOT NULL,
          task_description TEXT NOT NULL,
          reviewer TEXT NOT NULL,
          tenant TEXT NOT NULL,
          reviewer_kind TEXT NOT NULL CHECK(reviewer_kind='HUMAN_OWNER_TEST'),
          signed_at TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS editorial_no_update
          BEFORE UPDATE ON editorial_signoffs
          BEGIN SELECT RAISE(ABORT,'editorial_is_immutable');END;
        CREATE TRIGGER IF NOT EXISTS editorial_no_delete
          BEFORE DELETE ON editorial_signoffs
          BEGIN SELECT RAISE(ABORT,'editorial_is_immutable');END;
        """)

def sign_owner_editorial(gate,token,csrf,run_id,stepup_password):
    actor=gate.require(token,csrf)
    if actor["role"]!="OWNER":raise PermissionError("owner_editorial_required")
    with gate.store.db() as db:
        if not gate._verify_password(db,actor["login"],stepup_password):
            raise PermissionError("owner_editorial_stepup_required")
    case,candidate,grade,description=verified_candidate(run_id)
    ensure_tables(gate.store)
    with gate.store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        existing=db.execute(
          "SELECT model_run_id,reviewer,tenant FROM editorial_signoffs WHERE model_run_id=?",
          (run_id,)).fetchone()
        if existing:
            if existing["reviewer"]!=actor["login"] or existing["tenant"]!=actor["tenant"]:
                raise PermissionError("cross_tenant_editorial_signoff")
            return {"state":"EDITORIAL_SIGNED_BY_REAL_TEST_OWNER","model_run_id":run_id,
                    "evidence_id":case["evidence_id"],"task_description":description}
        db.execute("""INSERT INTO editorial_signoffs
          (model_run_id,evidence_id,evidence_sha256,result_sha256,rubric_version,
           task_description,reviewer,tenant,reviewer_kind,signed_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
           (run_id,case["evidence_id"],case["evidence_digest"],
            digest(candidate["response_json"]),VERSION,description,
            actor["login"],actor["tenant"],"HUMAN_OWNER_TEST",
            datetime.now(timezone.utc).isoformat()))
        gate.store._audit(db,"editorial:"+run_id,"OWNER_EDITORIAL_SIGNED",
            actor["login"],{"evidence_id":case["evidence_id"],
              "evidence_sha256":case["evidence_digest"],
              "rubric_version":VERSION,"response_sha256":digest(candidate["response_json"]),
              "external_action":False})
    return {"state":"EDITORIAL_SIGNED_BY_REAL_TEST_OWNER","model_run_id":run_id,
            "evidence_id":case["evidence_id"],"task_description":description}

def check_run_binding(store,run_id,actor=None):
    case,candidate,grade,description=verified_candidate(run_id)
    ensure_tables(store)
    with store.db() as db:
        signed=db.execute("SELECT * FROM editorial_signoffs WHERE model_run_id=?",(run_id,)).fetchone()
    if not signed or signed["reviewer_kind"]!="HUMAN_OWNER_TEST":
        raise ValueError("human_editorial_signoff_required")
    if actor and (actor["tenant"]!=signed["tenant"] or
                  actor["login"]!=signed["reviewer"]):
        raise PermissionError("owner_signoff_other_tenant")
    if (signed["evidence_id"]!=case["evidence_id"] or
        signed["evidence_sha256"]!=case["evidence_digest"] or
        signed["result_sha256"]!=digest(candidate["response_json"]) or
        signed["rubric_version"]!=VERSION or
        signed["task_description"]!=description):
        raise ValueError("signoff_provenance_mismatch")
    return case,candidate,description

def require_draft_allowed(gate,actor,draft_id):
    """Guard every NEW approval/execute irrespective of draft ID."""
    gate._owner_draft(actor,draft_id)
    gate.store.verify_audit()
    with gate.store.db() as db:
        draft=db.execute("SELECT * FROM drafts WHERE draft_id=?",(draft_id,)).fetchone()
        event=db.execute(
          "SELECT metadata FROM audit WHERE draft_id=? AND event='DRAFT_CREATED' ORDER BY sequence DESC LIMIT 1",
          (draft_id,)).fetchone()
    if not draft or not event:raise ValueError("draft_audit_not_found")
    meta=json.loads(event["metadata"])
    run_id=meta.get("source_model_run_id")
    if not run_id:raise ValueError("unbound_draft_is_not_approvable")
    case,candidate,description=check_run_binding(gate.store,run_id,actor)
    if (draft["evidence_id"]!=case["evidence_id"] or
        draft["evidence_sha256"]!=case["evidence_digest"] or
        draft["description"]!=description or
        meta.get("evidence_sha256")!=case["evidence_digest"]):
        raise ValueError("draft_model_evidence_or_task_mismatch")
    return {"run_id":run_id,"evidence_id":case["evidence_id"],
            "rubric_version":VERSION,"task_description":description}
