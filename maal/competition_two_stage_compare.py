"""Evidence-backed benchmark report: historical V3 vs genuinely NEW two-stage runs.

Reads persisted receipts, never invokes a model or confuses cached output with a
new inference. No invented time saving and no automated human editorial PASS.
"""
import json,statistics
from collections import defaultdict
from pathlib import Path
from maal.competition_run_paired import ROOT as OLD_ROOT
from maal.competition_two_stage_run import ROOT as NEW_ROOT
from maal.competition_two_stage_public import read_results

CASES=("fpt","skills","eu-ai")
def summarize():
    baseline=defaultdict(list)
    if OLD_ROOT.exists():
        for path in OLD_ROOT.glob("*/receipt.json"):
            try:
                obj=json.loads(path.read_text("utf8"))
                if (obj.get("schema")!="MAAL_PAIRED_QWEN_BENCH_V2" or
                    obj.get("model_key")!="1.7B" or
                    obj.get("prompt_version")!="V3" or obj.get("case") not in CASES):
                    continue
                baseline[obj["case"]].append(obj)
            except (ValueError,KeyError,OSError):continue
    read=read_results()
    new=defaultdict(list)
    for item in read["items"]:
        if item["case"] in CASES:new[item["case"]].append(item)
    cases=[]
    for key in CASES:
        old=baseline[key];fresh=new[key]
        def metric(rows,k):
            vals=[x.get(k) for x in rows if isinstance(x.get(k),(int,float))]
            return round(statistics.mean(vals),3) if vals else None
        cases.append({
          "case":key,
          "baseline_V3_Qwen1_7B":{"runs":len(old),
             "contract_valid":sum(1 for x in old if x.get("model_error") is None),
             "action_priority_contradictions":sum(1 for x in old if "no_action_must_have_none_priority" in str(x.get("model_error"))),
             "mean_inference_seconds":metric(old,"duration_seconds"),
             "mean_peak_memory_mb":metric(old,"peak_sampled_working_set_mb"),
             "editorially_approved":0},
          "two_stage_Qwen1_7B":{"fresh_runs":len(fresh),
             "structurally_actionable":sum(1 for x in fresh if x["quality"]["status"]=="CANDIDATE_FOR_INDEPENDENT_EDITORIAL"),
             "valid_abstentions":sum(1 for x in fresh if x["quality"]["status"]=="ABSTAIN_VALID"),
             "hold":sum(1 for x in fresh if x["quality"]["status"]=="HOLD"),
             "action_priority_contradictions":sum(1 for x in fresh if x["quality"].get("action_contradictions")),
             "mean_total_inference_seconds":metric(fresh,"total_seconds"),
             "mean_peak_memory_mb":metric(fresh,"memory_mb"),
             "editorially_approved":0},
        })
    complete=all(new[k] for k in CASES)
    return {"schema":"MAAL_TWO_STAGE_BENCH_COMPARISON_V1",
      "status":"EXPLORATORY_NO_EDITORIAL_ACCEPTANCE" if complete else "HOLD_NEW_LIVE_INFERENCE_NOT_RUN",
      "same_verified_cases":list(CASES),"baseline_runs_are_historical":True,
      "two_stage_requires_real_new_inference":True,
      "equal_scoring_claim":False,"reason":"Different output contracts, compare structural compliance, contradictions and editorial relevance separately.",
      "no_new_model_installed":True,"human_editorial_reviews_completed":False,
      "cases":cases}
if __name__=="__main__":
 print(json.dumps(summarize(),ensure_ascii=False,indent=2))
