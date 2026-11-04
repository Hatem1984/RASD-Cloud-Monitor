"""RASD real halfhour observations: QA only, NO SEND, NO secrets.

Scheduled records use ACTUAL GitHub runner start/end clocks. A missed
window remains missing, never reconstructed from RSS after the fact.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from datetime import datetime, date, time, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CAIRO=ZoneInfo("Africa/Cairo")
CODE_SHA="4d0217a2b1c0b15e3949c3e075fae31b9cb3e896"
EXPECTED_CRON="7,37 0-21 * * *"
REPO="Hatem1984/RASD-Pilot"
MAX_CANDIDATES=200

def settings_digest(s):
    return hashlib.sha256(json.dumps(s,sort_keys=True,ensure_ascii=False,
        separators=(",",":")).encode("utf-8")).hexdigest()

def load_config(manifest_path,baseline_path):
    m=json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    b=json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    s=m.get("settings")
    if (m.get("scope")!="QA_PREVIEW_NO_SEND" or m.get("schema_version")!=1
        or type(m.get("active_version")) is not int or
        not isinstance(s,dict) or settings_digest(s)!=m.get("sha256")):
        raise ValueError("untrusted_qa_manifest")
    sources=s.get("sources")
    baseline={x["id"]:x for x in b["feeds"]}
    if (not isinstance(sources,list) or len(sources)!=13
        or len(baseline)!=13 or len(set(x["id"] for x in sources))!=13
        or set(x["id"] for x in sources)!=set(baseline)):
        raise ValueError("source_inventory_mismatch")
    for src in sources:
        orig=baseline[src["id"]]
        if (type(src.get("enabled")) is not bool or not src["enabled"]
            or src["name"]!=orig["name"] or src["url"]!=orig["url"]):
            raise ValueError("source_not_approved")
    topics=s.get("topics")
    if not isinstance(topics,list) or len(topics)!=10:
        raise ValueError("topic_inventory_mismatch")
    for topic in topics:
        if (type(topic.get("enabled")) is not bool or
            topic.get("match") not in ("any","all") or
            not isinstance(topic.get("aliases"),list) or
            not all(isinstance(x,str) and len(x)>1 for x in topic["aliases"])):
            raise ValueError("topic_contract_invalid")
    if (s.get("start")!="00:00" or s.get("end")!="22:00"
        or s.get("scan_minutes")!=30 or s.get("send_at")!="22:00"):
        raise ValueError("owner_time_window_changed")
    kw=list(dict.fromkeys(alias for t in topics if t["enabled"]
                          for alias in t["aliases"]))
    if not kw:raise ValueError("no_approved_topics_enabled")
    return {**b,"keywords":kw},m

def slot_for(now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_aware_clock_required")
    local=now.astimezone(CAIRO)
    if local.hour>=22:return None
    return f"{local.hour:02d}:{(local.minute//30)*30:02d}"

def expected_slots():
    return [f"{h:02d}:{m:02d}" for h in range(22) for m in (0,30)]

def match_topics(item,setting,term_match):
    value=item["headline"]+" "+item.get("publisher_excerpt","")
    for t in setting["topics"]:
        if not t["enabled"]:continue
        matched=[term_match(value,[alias]) for alias in t["aliases"]]
        if all(matched) if t["match"]=="all" else any(matched):
            return True
    return False

def candidate(item,setting,now,monitor):
    if not match_topics(item,setting,monitor._ministry_term_present):
        return None
    stamped=parsedate_to_datetime(item["published"])
    if stamped is None or stamped.tzinfo is None:
        raise ValueError("publisher_timestamp_missing_zone")
    local=stamped.astimezone(CAIRO)
    if (local.date()!=now.astimezone(CAIRO).date()
        or not time(0,0)<=local.time().replace(tzinfo=None)<time(22,0)
        or stamped>now):
        return None
    if item["id"]!=monitor.article_id(item["url"]):
        raise ValueError("publisher_article_identity_invalid")
    return {k:item.get(k,"") for k in
            ("id","source","headline","url","publisher_excerpt")} | {
           "published_at_cairo":local.strftime("%Y-%m-%d %H:%M %Z"),
           "published_display_cairo":local.strftime("%Y-%m-%d %H:%M")}

def observe(*,mode,now,config,manifest,monitor,inspector=None,env=None):
    env=dict(os.environ if env is None else env)
    if mode not in ("probe","scheduled"):raise ValueError("unknown_observer_mode")
    if mode=="scheduled":
        if (env.get("GITHUB_REPOSITORY")!=REPO or
            env.get("GITHUB_REF")!="refs/heads/main" or
            env.get("GITHUB_EVENT_NAME")!="schedule" or
            env.get("GITHUB_EVENT_SCHEDULE")!=EXPECTED_CRON):
            raise ValueError("untrusted_schedule_event")
        if slot_for(now) is None:raise ValueError("outside_owner_window")
    sources=[f["id"] for f in config["feeds"]]
    if len(sources)!=13 or len(set(sources))!=13:
        raise ValueError("source_inventory_invalid")
    receipt={"schema_version":1,
        "kind":"QA_REAL_SLOT_OBSERVATION" if mode=="scheduled"
                else "QA_SMOKE_NO_COVERAGE",
        "day_cairo":now.astimezone(CAIRO).date().isoformat(),
        "slot_cairo":slot_for(now),
        "observed_at_utc":now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "finished_at_utc":None,
        "config_version":manifest["active_version"],
        "config_sha256":manifest["sha256"],
        "code_sha":env.get("RASD_QA_PUBLIC_COMMIT",CODE_SHA),
        "github_run_id":env.get("GITHUB_RUN_ID","local"),
        "source_ids":sources,"sources":[],"candidates":[],
        "status":"HOLD_NOT_INSPECTED",
        "smtp_sent":False,"original_screenshots_verified":False}
    try:
        scan=(inspector or monitor.inspect)(config,now=now,article_limit=MAX_CANDIDATES,
                                            require_complete_items=True)
        rows=scan["sources"]
        if ([x["feed_id"] for x in rows]!=sources or
            scan.get("matched_article_pool_truncated")):
            raise ValueError("source_list_or_candidate_pool_incomplete")
        receipt["sources"]=[{"id":r["feed_id"],"status":r["status"],
            "verified_links":r.get("verified_links",0),
            "failure_code":r.get("failure_code")} for r in rows]
        match=[candidate(x,manifest["settings"],now,monitor)
               for x in scan["matched_public_articles"]]
        items=[x for x in match if x is not None]
        if len({x["id"] for x in items})!=len(items):
            raise ValueError("duplicate_publisher_identity")
        receipt["candidates"]=items
        receipt["status"]=("OBSERVED_RSS_ALL_SOURCES" if
                           all(x["status"]=="ok" for x in rows) else
                           "HOLD_SOURCE_FAILURE")
    except Exception:
        receipt["status"]="HOLD_SCAN_INCOMPLETE"
    finished=datetime.now(timezone.utc)
    receipt["finished_at_utc"]=finished.isoformat(timespec="seconds")
    if mode=="scheduled" and (
        slot_for(finished)!=slot_for(now) or
        now.astimezone(CAIRO).minute%30>24):
        receipt["status"]="HOLD_MISSED_OR_CROSSED_WINDOW"
    return receipt

def audit_records(records,day,source_ids,config_version,expected_code_sha=CODE_SHA,expected_config_sha256=None):
    if isinstance(day,str):day=date.fromisoformat(day)
    slots={x:[] for x in expected_slots()}
    rejected=0
    for r in records:
        if not isinstance(r,dict) or r.get("kind")!="QA_REAL_SLOT_OBSERVATION":
            continue
        try:
            started=datetime.fromisoformat(r["observed_at_utc"])
            finished=datetime.fromisoformat(r["finished_at_utc"])
            slot=slot_for(started)
            if (r.get("schema_version")!=1 or r["day_cairo"]!=day.isoformat()
                or started.astimezone(CAIRO).date()!=day
                or finished.astimezone(CAIRO).date()!=day
                or slot is None or r["slot_cairo"]!=slot
                or slot_for(finished)!=slot
                or started.astimezone(CAIRO).minute%30>24
                or r.get("config_version")!=config_version
                or (expected_config_sha256 is not None and
                    r.get("config_sha256")!=expected_config_sha256)
                or r.get("code_sha")!=expected_code_sha
                or started.tzinfo is None or finished.tzinfo is None
                or finished<started
                or r.get("smtp_sent") is not False
                or r.get("original_screenshots_verified") is not False
                or r.get("source_ids")!=source_ids
                or [x["id"] for x in r["sources"]]!=source_ids
                or any(x["status"] not in ("ok","failed") for x in r["sources"])
                or len(r["candidates"])>MAX_CANDIDATES):
                raise ValueError("untrusted_record")
            from monitor import article_id
            for story in r["candidates"]:
                if (not isinstance(story,dict) or
                    not isinstance(story.get("url"),str) or
                    not story["url"].startswith("https://") or
                    story.get("id")!=article_id(story["url"]) or
                    not isinstance(story.get("headline"),str) or
                    not story["headline"] or
                    not isinstance(story.get("published_at_cairo"),str)):
                    raise ValueError("untrusted_candidate")
            slots[slot].append(r)
        except (ValueError,KeyError,TypeError,AttributeError):
            rejected+=1
    missing=[k for k,v in slots.items() if not v]
    failed=[k for k,v in slots.items() if v and any(
        r["status"]!="OBSERVED_RSS_ALL_SOURCES" or
        any(row["status"]!="ok" for row in r["sources"]) for r in v)]
    healthy=len(slots)-len(missing)-len(failed)
    candidate_ids=sorted({x["id"] for values in slots.values()
                         for r in values for x in r["candidates"]})
    complete=healthy==44 and rejected==0 and not missing and not failed
    return {"status":"PASS_44_REAL_RSS_WINDOWS" if complete
                else "HOLD_GAPS_OR_FAILED_SOURCES",
       "day_cairo":day.isoformat(),"complete":complete,
       "expected_slots":44,"observed_slots":44-len(missing),
       "healthy_slots":healthy,"missing_slots":missing,"failed_slots":failed,
       "rejected_records":rejected,
       "duplicate_attempts":sum(max(0,len(x)-1) for x in slots.values()),
       "observed_candidate_ids":candidate_ids,
       "smtp_sent":False,"original_screenshots_verified":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("probe","scheduled"),required=True)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--baseline",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    config,manifest=load_config(args.manifest,args.baseline)
    import monitor  # checked out from exact pinned RASD PR commit, no email
    now=datetime.now(timezone.utc)
    receipt=observe(mode=args.mode,now=now,config=config,
                    manifest=manifest,monitor=monitor)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RASD_STAGE2_OBSERVATION="+json.dumps({k:receipt[k] for k in
          ("kind","day_cairo","slot_cairo","status","config_version",
           "github_run_id","smtp_sent")},ensure_ascii=True),flush=True)
    print("RASD_STAGE2_SOURCE_OK="+str(sum(x["status"]=="ok" for x in receipt["sources"]))+"/13",flush=True)
    print("RASD_STAGE2_CANDIDATES="+str(len(receipt["candidates"])),flush=True)
    print("RASD_NO_SMTP=true",flush=True)
    if receipt["status"]=="HOLD_SCAN_INCOMPLETE":
        # The scheduled job must preserve a truthful HOLD artifact for the
        # daily reviewer, not silently disappear as an unspecified failed job.
        # A failed source does NOT count as an audited healthy slot.
        print("::warning::RASD_QA_SOURCE_SCAN_INCOMPLETE_HOLD",flush=True)
        if args.mode=="probe":
            raise SystemExit(3)

if __name__=="__main__":main()
