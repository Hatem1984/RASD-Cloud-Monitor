"""Re-use V0.3 report data as one read-only versioned historical QA snapshot.
No live RASD, Gmail, CAS, model calls, approval, production or publisher re-scrape.
"""
from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
import json,sys
PROJECT=Path(r"E:\MAAL")
APP=PROJECT/"01_ACTIVE_CODE"/"MAAL_UNIFIED_STAGING_SNAPSHOT_20261027"
sys.path.insert(0,str(APP))
from maal_web.server import get_case,CASE_IMAGE
base=json.loads((APP/"maal_web"/"product_report.json").read_text("utf8"))
assert base["mode"]=="HISTORICAL_LIMITED_REPORT"
assert base["signal_count"]==2 and len(base["stories"])==3
assert all(not s["ready_for_action"] for s in base["stories"])
case=get_case() # Gate E original JPEG hash verified directly in this call.
assert case["evidence_digest"]==sha256(CASE_IMAGE.read_bytes()).hexdigest()
folder=PROJECT/"04_HISTORICAL_QA"/"MAAL_UNIFIED_SNAPSHOT_REVIEW_20261027"
folder.mkdir(parents=True,exist_ok=True)
target=folder/"current.json"
if target.exists():
 old=json.loads(target.read_text("utf8"))
 assert old.get("snapshot_meta",{}).get("kind")=="HISTORICAL_READONLY_QA"
 previous=old["snapshot_meta"]["revision"]
else:previous=None
now=datetime.now(timezone.utc).isoformat()
base["snapshot_meta"]={
 "kind":"HISTORICAL_READONLY_QA",
 "generated_utc":now,
 "revision":sha256((now+case["evidence_digest"]).encode()).hexdigest()[:18],
 "prior_revision":previous,
 "last_successful_verified_original_observed_at":case["observed_at"],
 "source_new_verified_news_count":0,
 "source_live_connected":False,
 "coverage_basis":"3 historical Ministry documents grouped into two signals; original JPEG only for 17-Oct",
 "no_new_source_approval":True,
 "source_images_hold_for":["2026-10-24","2026-10-26"],
 "original_gate_e_sha256":case["evidence_digest"],
 "no_email_sent":True,
}
encoded=json.dumps(base,ensure_ascii=False,sort_keys=True,indent=2).encode("utf8")
tmp=folder/"current.json.tmp"
tmp.write_bytes(encoded);tmp.replace(target)
stamp={"revision":base["snapshot_meta"]["revision"],"prior_revision":previous,
 "snapshot_sha256":sha256(encoded).hexdigest(),"generated_utc":now,
 "source_count":3,"accepted_original_images":1,"new_verified_events":0,
 "report_file_version":"ROUND2_OWNER_REVIEW_V1_NO_NEW_EVIDENCE"}
(folder/"snapshot_generation_receipt.json").write_text(
 json.dumps(stamp,ensure_ascii=False,indent=2),encoding="utf8")
print("HISTORICAL_QA_SNAPSHOT_REFRESHED",json.dumps(stamp),flush=True)
