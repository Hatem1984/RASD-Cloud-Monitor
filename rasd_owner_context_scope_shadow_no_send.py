"""Compare exact publisher RSS baseline against owner-approved contextual scope.

Both passes reuse identical first-party RSS response bytes to avoid double
fetch / rate-limit. Read only, no candidate activation, no publisher images,
no Gmail, no recipient, no private ledger. Exact timestamps/hosts remain
mandatory. These are DISCOVERY counts only, not verified final reports.
"""
from __future__ import annotations

import json
import os
from datetime import datetime,timezone
from pathlib import Path

from monitor import inspect, read_feed


def main():
    if os.environ.get("RASD_AUTOMATION_ENABLED")!="false":
        raise RuntimeError("scope_live_audit_must_be_no_send")
    cfg=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    if cfg.get("context_scope")!="egypt_development_v1":
        raise RuntimeError("unapproved_scope_version")
    clock=datetime.now(timezone.utc)
    cache={}
    def fetch(url,bytes_limit):
        key=(url,bytes_limit)
        if key not in cache:
            cache[key]=read_feed(url,bytes_limit)
        return cache[key]
    original=os.environ.get("RASD_CONTEXT_SCOPE_ENABLED")
    try:
        os.environ["RASD_CONTEXT_SCOPE_ENABLED"]="false"
        baseline=inspect(cfg,fetch=fetch,now=clock,article_limit=200,
                         require_complete_items=True)
        os.environ["RASD_CONTEXT_SCOPE_ENABLED"]="true"
        contextual=inspect(cfg,fetch=fetch,now=clock,article_limit=200,
                           require_complete_items=True)
    finally:
        if original is None:
            os.environ.pop("RASD_CONTEXT_SCOPE_ENABLED",None)
        else:
            os.environ["RASD_CONTEXT_SCOPE_ENABLED"]=original
    from datetime import timedelta
    previous_end=clock.replace(minute=0,second=0,microsecond=0)
    previous_start=previous_end-timedelta(hours=1)
    from email.utils import parsedate_to_datetime
    context_items=contextual["matched_public_articles"]
    added=[i for i in context_items if
           i.get("match_origin")=="contextual_topic_title"]
    last_hour=sum(previous_start <=
                  parsedate_to_datetime(i["published"]).astimezone(timezone.utc)
                  < previous_end for i in added)
    print("RASD_OWNER_CONTEXT_BASELINE_UNVERIFIED_RSS_MATCHES="+
          str(baseline["planning_headline_matches"]))
    print("RASD_OWNER_CONTEXT_TOTAL_UNVERIFIED_RSS_MATCHES="+
          str(contextual["planning_headline_matches"]))
    print("RASD_OWNER_CONTEXT_ADDED_LAST72H_UNVERIFIED_RSS_MATCHES="+
          str(contextual["contextual_topic_matches_unverified_images"]))
    print("RASD_OWNER_CONTEXT_ADDED_PREVIOUS_HOUR_UNVERIFIED_RSS_MATCHES="+
          str(last_hour))
    print("RASD_OWNER_CONTEXT_RSS_SOURCES_OK="+str(sum(
          x["status"]=="ok" for x in contextual["sources"])))
    print("RASD_OWNER_CONTEXT_SCOPE_NOT_ACTIVATED_ON_PRODUCTION=1")
    print("RASD_OWNER_CONTEXT_NO_ORIGINAL_PHOTO_PROOF_NO_SMTP=1")


if __name__=="__main__":
    main()
