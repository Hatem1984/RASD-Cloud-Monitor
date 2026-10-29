"""Prepare one new OFFICIAL-source owner draft. Never approve or execute.

Run manually in the owner's isolated Windows environment only after a real
verified capture and a valid saved Qwen freeform inference. Reads private
test account credentials in memory; never logs secrets or stores sessions.
"""
from pathlib import Path
from datetime import date,datetime
import sqlite3
import json

from maal.operator_gateway import OperatorGateway
from maal.decision_contracts import Evidence
from maal.competition_new_source import ROOT,get_case_from_capture
from maal.competition_new_reasoning import verified_runs

DB=Path("E:/MAAL/04_HISTORICAL_QA/MAAL_GATE_H_E2E_20261027/operator.sqlite")
CREDS=Path("E:/MAAL/02_PRIVATE_OWNER/MAAL_GATE_F_TEST_CREDENTIALS_20261027.txt")
OLD="425b5640-c656-4838-98dc-f2ee477f74da"
FPT="d1c139413b2c9a1c07432ce1"

def owner_account(login:str):
    accounts=[];account={}
    for line in CREDS.read_text("utf-8-sig").splitlines():
        if ":" not in line:continue
        key,value=line.split(":",1);key=key.strip()
        if key=="Login":
            if account:accounts.append(account)
            account={"Login":value.strip()}
        elif key in ("Password","Role"):
            account[key]=value.strip()
    if account:accounts.append(account)
    found=[x for x in accounts if x.get("Login")==login and
           x.get("Role")=="OWNER" and x.get("Password")]
    if len(found)!=1:raise RuntimeError("test_owner_creds_not_unambiguous")
    return found[0]

def main():
    gate=OperatorGateway(DB)
    with gate.store.db() as db:
        old=db.execute("SELECT state FROM drafts WHERE draft_id=?",(OLD,)).fetchone()
        old_tasks=db.execute("SELECT count(*) FROM tasks WHERE draft_id=?",(OLD,)).fetchone()[0]
        matching_owner=db.execute(
            "SELECT login FROM demo_task_owners WHERE draft_id=?",(OLD,)).fetchone()
        if not old or old["state"]!="EXECUTED" or old_tasks!=1 or not matching_owner:
            raise RuntimeError("prior_owner_workflow_invariant_hold")
        login=matching_owner["login"]
    case=get_case_from_capture(ROOT/FPT)
    fresh=next((r for r in verified_runs() if
        r["evidence_id"]==FPT and
        r["status"]=="EVIDENCE_GROUNDED_GENERATIVE_DRAFT"),None)
    if not fresh or fresh.get("human_editorial_approval") is True:
        raise RuntimeError("not_a_pending_real_qwen_draft")
    proposal=fresh["analysis"]["recommendation"]
    if not isinstance(proposal,str) or not 8<=len(proposal)<=500:
        raise ValueError("unsafe_model_recommendation")
    ev=Evidence(
      case["evidence_id"],case["publisher"],case["original_url"],
      case["headline"],date.fromisoformat(case["published_day"]),
      datetime.fromisoformat(case["observed_at"]),
      case["evidence_digest"],case["verification_status"])
    ev.validate()
    # Owner authentication is needed only to prepare a review draft.
    # AUTHORIZATION to approve is a separate human password re-entry.
    secret=owner_account(login)
    token,csrf=gate.login(secret["Login"],secret["Password"])
    try:
        key="maal-new-case-"+case["evidence_id"]+"-"+fresh["run_id"]
        draft=gate.create(token,csrf,ev,proposal,key,model_run_id=fresh["run_id"])
    finally:
        gate.logout(token)
    with gate.store.db() as db:
        record=db.execute(
            "SELECT state,evidence_id,evidence_sha256,approved_by FROM drafts WHERE draft_id=?",
            (draft,)).fetchone()
        tasks=db.execute("SELECT COUNT(*) FROM tasks WHERE draft_id=?",(draft,)).fetchone()[0]
        prior=db.execute("SELECT state FROM drafts WHERE draft_id=?",(OLD,)).fetchone()
        old_tasks_after=db.execute(
            "SELECT COUNT(*) FROM tasks WHERE draft_id=?",(OLD,)).fetchone()[0]
        owner=db.execute("SELECT login FROM demo_task_owners WHERE draft_id=?",(draft,)).fetchone()
    if (not record or record["state"]!="DRAFT" or
        record["evidence_id"]!=case["evidence_id"] or
        record["evidence_sha256"]!=case["evidence_digest"] or
        record["approved_by"] is not None or tasks!=0 or
        prior["state"]!="EXECUTED" or old_tasks_after!=1 or
        owner["login"]!=login):
        raise RuntimeError("new_draft_postcondition_hold")
    print(json.dumps({
      "status":"NEW_OFFICIAL_EVIDENCE_OWNER_DRAFT_PREPARED_UNAPPROVED",
      "draft_id":draft,"original_gate_h_unchanged":True,
      "new_source_evidence_id":case["evidence_id"],
      "verified_original_image_sha256":case["evidence_digest"],
      "actual_local_qwen_run_id":fresh["run_id"],
      "draft_state":"DRAFT","new_tasks":0,
      "owner_approval_performed":False,"external_action":False,
    },ensure_ascii=False))

if __name__=="__main__":
    main()
