"""Read-only independent Qwen3 two-stage receipts for the existing MA'AL UI.

No run is a human editorial signoff. The operator approval API remains unchanged
and does NOT accept two-stage output as an authorized decision by itself.
"""
from __future__ import annotations
import json,re
from pathlib import Path
from maal.competition_new_source import ROOT as EVIDENCE_ROOT,get_case_from_capture
from maal.competition_two_stage_run import ROOT as RUN_ROOT
from maal.competition_two_stage_contract import (
 VERSION,COMPANY,validate_stage_one,validate_stage_two,frozen_acceptance)
def read_results():
    out=[];invalid=0
    if RUN_ROOT.exists():
        for folder in RUN_ROOT.iterdir():
            if not folder.is_dir() or not re.fullmatch(r"maal-two-stage-[0-9a-f]{32}",folder.name):
                continue
            try:
                rec=json.loads((folder/"receipt.json").read_text("utf8"))
                if (rec.get("schema")!="MAAL_TWO_STAGE_REASONING_V1" or
                    rec.get("run_id")!=folder.name or rec.get("version")!=VERSION or
                    rec.get("company_key")!=COMPANY or
                    rec.get("human_approved") is not False or rec.get("executed") is not False):
                    raise ValueError("receipt_contract")
                case=get_case_from_capture(EVIDENCE_ROOT/rec["source_id"])
                if case["evidence_digest"]!=rec["source_sha256"] or case["original_url"]!=rec["source_url"]:
                    raise ValueError("evidence_changed")
                first=json.loads((folder/"stage1.json").read_text("utf8"))
                s1=first.get("output")
                s1_valid=(first.get("error") is None and s1 is not None)
                if s1_valid:validate_stage_one(case,s1)
                second=None;s2=None
                if rec["stage2_called"]:
                    second=json.loads((folder/"stage2.json").read_text("utf8"))
                    s2=second.get("output")
                    if second.get("error") is None and s2 is not None:
                        validate_stage_two(case,s2,s1,folder.name)
                # A claimed abstention may never have an action artifact.
                if (s1_valid and s1["outcome"]!="ACTION_WORTH_REVIEW"
                      and (rec["stage2_called"] or (folder/"stage2.json").exists())):
                    raise ValueError("abstention_with_action")
                grade=frozen_acceptance(case,s1 if s1_valid else None,
                    s2 if second and second.get("error") is None else None,
                    first.get("error"),second.get("error") if second else None,folder.name)
                if grade!=rec.get("quality"):raise ValueError("quality_mismatch")
                out.append({"case":case["source_key"],"publisher":case["publisher"],
                    "headline":case["headline"],"published_day":case["published_day"],
                    "run_id":folder.name,"source_id":case["evidence_id"],
                    "source_url":case["original_url"],"outcome":rec["stage1_outcome"],
                    "stage1_result":s1 if s1_valid else None,
                    "stage2_result":s2 if second and second.get("error") is None else None,
                    "quality":grade,"total_seconds":rec["total_seconds"],
                    "memory_mb":rec.get("peak_memory_mb"),"stage2_called":rec["stage2_called"],
                    "model":rec["model"],"recorded_at":rec["recorded_at"],
                    "editorial_status":"NOT_REVIEWED","can_approve":False,
                    "can_execute":False})
            except (OSError,ValueError,KeyError,TypeError):
                invalid+=1
    out.sort(key=lambda x:x["recorded_at"],reverse=True)
    return {"schema":"MAAL_TWO_STAGE_READONLY_RESULTS_V1",
      "rubric_version":VERSION,"items":out,"invalid_receipts":invalid,
      "human_editorial_approved":False,"owner_approved":False,
      "external_actions":False,"live_inference_now":False}
