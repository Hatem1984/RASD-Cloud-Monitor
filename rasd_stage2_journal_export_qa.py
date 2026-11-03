"""Convert ONLY COMPLETE real private Actions evidence to the existing RASD
private day-journal format, for human review. NEVER push it or email it.
"""
from __future__ import annotations
import json
from datetime import date, datetime
from rasd_stage2_observer_qa import audit_records
from rasd_owner_evidence_journal import new_day,add_observation,audit_day

def reviewed_day_journal(receipts,day,source_ids,config_version,
                         *,expected_code_sha,expected_config_sha256):
    if isinstance(day,str):day=date.fromisoformat(day)
    result=audit_records(receipts,day,source_ids,config_version,
        expected_code_sha=expected_code_sha,
        expected_config_sha256=expected_config_sha256)
    if not result["complete"]:
        return {"status":"HOLD_NO_PRIVATE_JOURNAL_EXPORT","audit":result},None
    doc=new_day(day)
    eligible=[r for r in receipts if r.get("kind")=="QA_REAL_SLOT_OBSERVATION"
              and r.get("day_cairo")==day.isoformat()]
    eligible.sort(key=lambda x:(x["observed_at_utc"],x["github_run_id"]))
    for r in eligible:
        # Reuse original immutable actual observed clock; NEVER assign
        # nominal cron time, and do not backfill a missed GitHub job.
        rows=[{"feed_id":x["id"],"status":x["status"]}
              for x in r["sources"]]
        doc=add_observation(doc,now=datetime.fromisoformat(r["observed_at_utc"]),
            source_health=rows,candidate_stories=r["candidates"],
            expected_source_ids=source_ids,config_version=config_version)
    checked=audit_day(doc,day,source_ids)
    if not checked["complete"]:
        raise RuntimeError("owner_existing_journal_disagrees_with_immutable_evidence")
    return {"status":"READY_PRIVATE_DAY_JOURNAL_QA_REVIEW_ONLY",
            "slots":len(doc["slots"]),"articles":len(doc["articles"]),
            "smtp_sent":False,"private_repo_written":False},doc
