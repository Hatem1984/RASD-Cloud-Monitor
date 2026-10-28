"""Run three INDEPENDENT fresh Qwen inferences once, same frozen rubric.

Sidecar acceptance is intentionally not the owner DRAFT and never performs
approval. Stores model receipt, start/end, rubric version and real timings in
the authorized owner's E: private QA folder. Historical run IDs are forbidden.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json,os
from maal.competition_new_source import ROOT, SOURCES, verified_cases
from maal.competition_new_reasoning import (
    RUN_ROOT,run_new_case,COMPANY
)
from maal.competition_frozen_rubric import (
    RUBRIC_VERSION, COMPETITION_SCENARIOS, evaluate
)
BENCH=Path("E:/MAAL/04_HISTORICAL_QA/MAAL_COMPETITION_MVP_20261028/frozen_quality_benchmark_20261028")

def main():
    BENCH.mkdir(parents=True,exist_ok=True)
    files=list(BENCH.glob("*.json"))
    if files: raise RuntimeError("fresh_independent_benchmark_already_run_no_rerun")
    cases={c["source_key"]:c for c in verified_cases()}
    if set(COMPETITION_SCENARIOS)-set(cases):
        raise ValueError("missing_real_publisher_evidence")
    for key in ("fpt","skills","eu-ai"):
        case=cases[key]
        result=run_new_case(case["evidence_id"])
        if result["model_started"] is not True:
            raise ValueError("model_not_called")
        answer=result["analysis"]
        if answer is None:
            raw=RUN_ROOT/result["run_id"]/"raw_model_output.json"
            if raw.is_file():
                try:
                    from json import loads
                    answer=loads(loads(raw.read_text("utf8"))["choices"][0]["message"]["content"])
                except (ValueError,KeyError,TypeError,IndexError):answer=None
        grade=evaluate(case,answer,result["error"])
        assessment={
            "schema":"MAAL_FROZEN_NEW_MODEL_ASSESSMENT_V1",
            "case":key,"scenario":COMPETITION_SCENARIOS[key],
            "source_publisher":case["publisher"],"source_url":case["original_url"],
            "published_day":case["published_day"],
            "evidence_id":case["evidence_id"],
            "original_page_sha256":case["evidence_digest"],
            "fresh_model_run_id":result["run_id"],
            "qwen3_status":result["status"],"rubric_version":RUBRIC_VERSION,
            "automated_acceptance":grade.objective_result,
            "dimensions":grade.dimensions,
            "score":grade.score,"maximum":grade.max_score,
            "human_editorial_approval":False,
            "rubric_notes":grade.notes,
            "model_wall_seconds":result["elapsed_seconds"],
            "token_usage":result["token_usage"],
            "model_error":result["error"],
            "new_decision_draft_created":False,
            "human_approved":False,"executed":False,"smtp_sent":False,
            "saved_at":datetime.now(timezone.utc).isoformat(),
        }
        name=BENCH/(key+".json")
        with name.open("x",encoding="utf8") as output:
            json.dump(assessment,output,ensure_ascii=False,indent=2)
            output.flush();os.fsync(output.fileno())
        print(json.dumps({
            "case":key,"model_run_id":result["run_id"],
            "model_status":result["status"],
            "evaluation":grade.objective_result,
            "score":grade.score,"max_score":grade.max_score,
            "seconds":result["elapsed_seconds"],
            "tokens":result["token_usage"]["total_tokens"] if result["token_usage"] else None,
            "error":result["error"],
        },ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
