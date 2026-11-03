"""Owner-only evidence journal in the EXISTING private GitHub repository.

A journal is the bounded proof that every Cairo 30m slot and every configured
source was actually inspected. Its candidate IDs are observations, not approved
news or publisher screenshots. Incomplete journals force final digest HOLD.
No SMTP, no Gmail, no production activation in this module.
"""
from __future__ import annotations
import base64
import json
import re
import ssl
from datetime import datetime,date,time,timedelta,timezone
from urllib.error import HTTPError
from urllib.request import Request, HTTPSHandler, build_opener
from delivery_bridge import NoGitHubRedirect,PRIVATE_REPO,PRIVATE_BRANCH

from daily_report import CAIRO

def slot_name(now:datetime):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("owner_journal_timezone_required")
    local=now.astimezone(CAIRO)
    return f"{local.hour:02}:{(local.minute//30)*30:02}"

def complete_slot_names():
    return [f"{hour:02}:{minute:02}" for hour in range(22) for minute in (0,30)]

def new_day(day:date):
    return {"schema_version":1,"day_cairo":day.isoformat(),"slots":{},"articles":{}}

def validate_journal(doc,day:date):
    if (not isinstance(doc,dict) or set(doc)!={"schema_version","day_cairo","slots","articles"}
            or doc["schema_version"]!=1 or doc["day_cairo"]!=day.isoformat()
            or not isinstance(doc["slots"],dict) or len(doc["slots"])>44
            or not isinstance(doc["articles"],dict) or len(doc["articles"])>200):
        raise ValueError("journal_shape_hold")
    valid_slots=set(complete_slot_names())
    from monitor import article_id
    for key,article in doc["articles"].items():
        if (not isinstance(key,str) or not re.fullmatch(r"[a-f0-9]{24}",key)
                or not isinstance(article,dict) or article.get("id")!=key
                or article_id(article.get("url",""))!=key
                or any(not isinstance(article.get(k),str) or not article[k]
                       for k in ("headline","url","source","published_at_cairo","published_display_cairo"))):
            raise ValueError("journal_article_provenance_hold")
    for slot,record in doc["slots"].items():
        if (slot not in valid_slots or not isinstance(record,dict)
                or set(record)!={"sources","candidate_ids","observed_at_utc","config_version"}
                or not isinstance(record["sources"],dict)
                or not isinstance(record["candidate_ids"],list)
                or any(not isinstance(v,str) or not re.fullmatch(r"[a-f0-9]{24}",v)
                       for v in record["candidate_ids"])
                or len(record["candidate_ids"])!=len(set(record["candidate_ids"]))
                or any(x not in doc["articles"] for x in record["candidate_ids"])
                or not isinstance(record["config_version"],int)
                or not isinstance(record["observed_at_utc"],str)
                or any(v not in ("ok","failed") for v in record["sources"].values())):
            raise ValueError("journal_entry_hold")
    return doc

def add_observation(doc,*,now:datetime,source_health:list[dict],candidate_stories:list[dict],
                    expected_source_ids:list[str],config_version:int):
    local=now.astimezone(CAIRO)
    day=local.date()
    if not time(0,0)<=local.time()<time(22,0):
        raise ValueError("journal_outside_owner_scan_period")
    out=json.loads(json.dumps(validate_journal(doc,day)))
    if ([row.get("feed_id") for row in source_health]!=expected_source_ids
            or len(set(expected_source_ids))!=len(expected_source_ids)
            or not expected_source_ids):
        raise ValueError("journal_source_inventory_hold")
    statuses={s["feed_id"]:s["status"] for s in source_health}
    if any(v not in ("ok","failed") for v in statuses.values()):
        raise ValueError("journal_source_status_hold")
    from monitor import article_id
    for story in candidate_stories:
        if (not isinstance(story,dict) or not isinstance(story.get("id"),str)
                or article_id(story.get("url",""))!=story["id"]):
            raise ValueError("journal_candidate_id_hold")
        selected={k:story.get(k,"") for k in (
            "id","headline","url","source","published_at_cairo",
            "published_display_cairo","publisher_excerpt")}
        old=out["articles"].get(story["id"])
        if old is not None and old!=selected:
            raise ValueError("journal_changed_story_identity_hold")
        out["articles"][story["id"]]=selected
    candidate_ids=[x["id"] for x in candidate_stories]
    slot=slot_name(now)
    observed=now.astimezone(timezone.utc).isoformat(timespec="seconds")
    if slot in out["slots"]:
        old=out["slots"][slot]
        if set(old["sources"])!=set(expected_source_ids):
            raise ValueError("journal_source_identity_changed_same_slot")
        statuses={k:("ok" if old["sources"][k]=="ok" or statuses[k]=="ok" else "failed")
                  for k in expected_source_ids}
        candidate_ids=list(sorted(set(candidate_ids)|set(old["candidate_ids"])))
    else:
        candidate_ids=list(sorted(set(candidate_ids)))
    out["slots"][slot]={"sources":statuses,"candidate_ids":candidate_ids,
                         "observed_at_utc":observed,"config_version":config_version}
    validate_journal(out,day)
    return out

def audit_day(doc,day:date,expected_source_ids:list[str]):
    try:
        validate_journal(doc,day)
    except (ValueError,TypeError):
        return {"status":"HOLD_JOURNAL_INVALID","complete":False}
    slots=set(doc["slots"])
    missing=sorted(set(complete_slot_names())-slots)
    failure=[slot for slot,x in doc["slots"].items()
             if set(x["sources"])!=set(expected_source_ids)
             or any(x["sources"].get(k)!="ok" for k in expected_source_ids)]
    observed=sorted(set(x for row in doc["slots"].values()
                        for x in row["candidate_ids"]))
    if set(observed)!=set(doc["articles"]):
        return {"status":"HOLD_JOURNAL_ORPHAN_ARTICLES","complete":False}
    return {"status":"PASS_OBSERVED_RSS_SLOTS" if not missing and not failure
            else "HOLD_GAPS_IN_OBSERVED_RSS",
            "complete":not missing and not failure,
            "missing_slots":missing,"failed_slots":sorted(failure),
            "observed_candidate_ids":observed,
            "articles":[doc["articles"][k] for k in observed],
            "expected_slots":len(complete_slot_names())}

class PrivateDayJournal:
    """Single-file bounded GitHub Contents CAS, no secrets exposed in errors."""
    def __init__(self,token:str):
        if not isinstance(token,str) or len(token)<16:
            raise RuntimeError("journal_secret_missing")
        self._token=token
        self._opener=build_opener(NoGitHubRedirect(),
                                  HTTPSHandler(context=ssl.create_default_context()))
    def _request(self,method,url,content=None):
        body=None if content is None else json.dumps(content).encode()
        req=Request(url,method=method,data=body,headers={
            "Authorization":"Bearer "+self._token,
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28",
            "User-Agent":"RASD-owner-private-day-journal",
            "Content-Type":"application/json"})
        try:
            with self._opener.open(req,timeout=18) as result:
                raw=result.read(250_001)
            if len(raw)>250_000:
                raise ValueError("journal_response_too_large")
            return json.loads(raw.decode("utf-8"))
        except HTTPError as error:
            if method=="GET" and error.code==404:
                return None
            raise RuntimeError("private_journal_request_hold") from None
        except Exception:
            raise RuntimeError("private_journal_request_hold") from None
    def _url(self,day):
        return f"https://api.github.com/repos/{PRIVATE_REPO}/contents/evidence/rasd-day-{day.isoformat()}.json"
    def read(self,day:date):
        payload=self._request("GET",self._url(day)+"?ref="+PRIVATE_BRANCH)
        if payload is None:
            return new_day(day),None
        if (payload.get("type")!="file" or payload.get("encoding")!="base64"
            or not isinstance(payload.get("sha"),str)):
            raise RuntimeError("private_journal_envelope_hold")
        try:
            decoded=json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
            return validate_journal(decoded,day),payload["sha"]
        except Exception:
            raise RuntimeError("private_journal_decode_hold") from None
    def record(self,*,now,source_health,candidate_stories,expected_source_ids,
               config_version):
        day=now.astimezone(CAIRO).date()
        before,sha=self.read(day)
        after=add_observation(before,now=now,source_health=source_health,
             candidate_stories=candidate_stories,expected_source_ids=expected_source_ids,
             config_version=config_version)
        if after==before:
            return after
        encoded=base64.b64encode((json.dumps(after,ensure_ascii=False,indent=2)+"\n").encode()).decode()
        commit={"message":"rasd owner: record one bounded source observation",
                "branch":PRIVATE_BRANCH,"content":encoded}
        if sha:commit["sha"]=sha
        response=self._request("PUT",self._url(day),commit)
        if not response or not isinstance(response.get("commit",{}).get("sha"),str):
            raise RuntimeError("private_journal_commit_unverified")
        actual,new_sha=self.read(day)
        if actual!=after or not new_sha or new_sha==sha:
            raise RuntimeError("private_journal_readback_hold")
        return actual
