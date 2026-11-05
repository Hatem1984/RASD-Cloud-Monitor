"""All 13 public native RSS checks on the actual GitHub cloud runner.

No email, no private ledger, no owner settings writes, no screenshot fallback.
A PASS means only this one inspection succeeded; NOT whole-day completeness.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from monitor import inspect

ROOT=Path(__file__).parent
cfg=json.loads((ROOT/"sources_owner_daily_qa.json").read_text(encoding="utf-8"))
assert len(cfg["feeds"])==13
assert len({f["id"] for f in cfg["feeds"]})==13
now=datetime.now(timezone.utc)
try:
    result=inspect(cfg,now=now,article_limit=200,require_complete_items=True)
except Exception as error:
    print("RASD_CLOUD_FULL_SOURCES=HOLD_ALL_FETCHES",flush=True)
    print("RASD_CLOUD_NO_SMTP=true",flush=True)
    raise SystemExit(0)
summary=[]
for item in result["sources"]:
    summary.append({"id":item["feed_id"],"status":item["status"],
                    "verified_links":item["verified_links"],
                    "failure_code":item.get("failure_code")})
print("RASD_CLOUD_FULL_SOURCE_ROWS="+json.dumps(summary,sort_keys=True),flush=True)
healthy=sum(row["status"]=="ok" for row in summary)
state=("PASS_ONCE_NOT_DAY_PROOF" if healthy==13 and len(summary)==13
       else "HOLD_INCOMPLETE_SOURCE_COVERAGE")
print("RASD_CLOUD_FULL_SOURCES="+state,flush=True)
print("RASD_CLOUD_HEALTHY_SOURCES="+str(healthy)+"/13",flush=True)
print("RASD_CLOUD_NO_SMTP=true",flush=True)
