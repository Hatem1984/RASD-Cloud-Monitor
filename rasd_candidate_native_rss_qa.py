"""First-party live admission trial for owner-prioritized 100-source research.
No SMTP, no archive, no new production source, no article text or URLs in log.
RSS strict dates and original publisher identity are tested before any
possible screenshot QA. Failed feeds are not silently called active.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from monitor import parse_rss, read_feed

CANDIDATES = (
    ("soutalomma", "صوت الأمة", "https://www.soutalomma.com/rss/rss",
     ("www.soutalomma.com", "soutalomma.com")),
    ("almal", "المال", "https://almalnews.com/rss/rss/",
     ("almalnews.com", "www.almalnews.com")),
    ("youm7", "اليوم السابع", "https://www.youm7.com/rss/SectionRss?SectionID=319",
     ("www.youm7.com",)),
    ("youm7_economy", "اليوم السابع - الاقتصاد", "https://www.youm7.com/rss/SectionRss?SectionID=297",
     ("www.youm7.com",)),
)
MAX_BYTES=1_500_000
def try_source(entry, keywords, now, fetch=read_feed):
    sid, name, url, hosts=entry
    result={"publisher_id":sid,"status":"HOLD","original_rss_links":0,
            "matched_with_saved_terms":0,"original_jpeg_verified":False,
            "reason":"not_checked"}
    try:
        raw=fetch(url,MAX_BYTES)
        count,matches=parse_rss(raw,{"id":sid,"name":name,"url":url,
                 "allowed_article_hosts":list(hosts)},keywords,
                 now=now,recent_hours=72,require_complete_items=True)
        if not 1<=count<=500:
            result["reason"]="feed_has_no_complete_items"
        else:
            result.update(status="RSS_ONLY_NOT_SCREENSHOT_APPROVED",
                          original_rss_links=count,
                          matched_with_saved_terms=len(matches),
                          reason="original_screenshot_and_review_still_required")
    except Exception as error:
        cause=str(error) if type(error) in (ValueError,RuntimeError) else ""
        approved={"feed_redirect_blocked","not_rss","DTD_or_entity_forbidden",
            "rss_channel_unverifiable","rss_original_item_date_unverifiable",
            "rss_original_item_identity_unverifiable",
            "rss_original_duplicate_conflict","feed_endpoint_not_reviewed",
            "rss_size_limit_exceeded"}
        result["reason"]=cause if cause in approved else (
            type(error).__name__ if type(error).__name__ in
            ("HTTPError","URLError","TimeoutError","ParseError","RuntimeError",
             "ValueError") else "other")
    return result

def main():
    config=json.loads(Path("sources_newsroom_active.json").read_text(encoding="utf-8"))
    existing={f["id"] for f in config["feeds"]}
    if existing.intersection({x[0] for x in CANDIDATES}) or len(existing)!=13:
        raise RuntimeError("not_a_new_qualified_candidate")
    now=datetime.now(timezone.utc)
    results=[try_source(e,config["keywords"],now) for e in CANDIDATES]
    print(json.dumps({
        "mode":"RASD_NEW_PUBLISHER_ORIGINAL_RSS_NO_SEND",
        "candidates":results,
        "approved_automated_feeds_unchanged":13,
        "sources_activated":0,"images_claimed":0,
        "private_ledger_changed":False,"emails_sent":0,
    },sort_keys=True,ensure_ascii=False))

if __name__=="__main__":
    main()
