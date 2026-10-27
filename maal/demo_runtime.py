"""Gate H: local verified historical evidence -> fresh Qwen3; no actions or approvals."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, date, timezone
import json, uuid, os, threading, time
from maal.ai_decision_engine import analyze, LocalLlamaCppProvider, CompanyProfile
from maal.decision_contracts import Evidence, BusinessContext
LOCK=threading.Lock()
LAST_RUN=0.0
COOLDOWN_SECONDS=12
def infer_to_local_receipt(case:dict, path:Path)->dict:
 global LAST_RUN
 if not LOCK.acquire(blocking=False):
  raise RuntimeError("real_ai_analysis_already_running")
 try:
  if time.monotonic()-LAST_RUN<COOLDOWN_SECONDS:
   raise RuntimeError("model_run_cooldown")
  # The source is already independently validated by get_case(), which
  # compares the original-page JPEG with the owner Gate E receipt.
  if (case.get("timeliness")!="HISTORICAL" or
      case.get("verified_receipt") is not True or
      case.get("verification_status")!="VERIFIED_ORIGINAL_PAGE"):
   raise ValueError("expected_historical_verified_evidence")
  evidence=Evidence(case["evidence_id"],case["publisher"],case["original_url"],
    case["finding"],date.fromisoformat(case["published_day"]),
    datetime.fromisoformat(case["observed_at"]),case["evidence_digest"],
    case["verification_status"])
  profile=CompanyProfile(
    BusinessContext("SYNTHETIC_EGYPT_INFRA",
      "البنية التحتية والطاقة المتجددة","مصر"),
    "مراجعة هذا الدليل الحكومي التاريخي للشركة الافتراضية؛ لا افتراض للأهلية أو المنفعة المالية.",
    ("infrastructure","renewable_energy"),synthetic=True)
  provider=LocalLlamaCppProvider()
  analysis=analyze(profile,(evidence,),provider)
  if analysis["action_executed"] or not analysis["human_approval_required"]:
   raise ValueError("ai_authority_violation")
  run_id="maal-g3-"+uuid.uuid4().hex
  result={"timestamp_utc":datetime.now(timezone.utc).isoformat(),
    "run_id":run_id,"model":provider.model,"backend":"llama.cpp CPU localhost",
    "company":"SYNTHETIC_EGYPT_INFRA","real_local_inference":True,
    "evidence_id":case["evidence_id"],"original_digest":case["evidence_digest"],
    "cloud_api_cost_usd":0.0,"accepted_by_contract":True,
    "inference_seconds":provider.last_elapsed_seconds,
    "provider_usage":provider.last_usage,"analysis":analysis,
    "human_review":"HOLD","external_actions_executed":False}
  path.parent.mkdir(parents=True,exist_ok=True)
  # Immutable per-run evidence receipt for reproducible competition audit.
  archive=path.parent/"runs"
  archive.mkdir(parents=True,exist_ok=True)
  permanent=archive/(run_id+".json")
  with open(permanent,"x",encoding="utf8") as f:
   json.dump(result,f,ensure_ascii=False,indent=2)
   f.flush();os.fsync(f.fileno())
  latest=path.with_suffix(".part")
  with open(latest,"x",encoding="utf8") as f:
   json.dump(result,f,ensure_ascii=False,indent=2)
   f.flush();os.fsync(f.fileno())
  os.replace(latest,path)
  LAST_RUN=time.monotonic()
  return {"run_id":run_id,"elapsed_seconds":provider.last_elapsed_seconds,
    "tokens":provider.last_usage.get("total_tokens"),
    "started_before_result":True,"cloud_api_cost_usd":0.0}
 finally:
  LOCK.release()
