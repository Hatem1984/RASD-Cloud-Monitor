"""Read-only original Masrawy RSS-vs-publisher timestamp diagnosis.

Original feeds may have naive date text. Accept NO naive dates. At most six
reviewed first-party article pages are checked for exact title, local wall
clock and NewsArticle JSON-LD explicit time zone. Never log article title,
original URLs, HTML or upstream exception bodies. NO SEND.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from monitor import read_feed
from masrawy_original_date import original_pubdate

KNOWN_HOLD = frozenset({
    "masrawy_original_url_not_approved",
    "masrawy_original_page_redirect_forbidden",
    "masrawy_original_page_unavailable",
    "masrawy_original_page_size_hold",
    "masrawy_original_page_request_hold",
    "masrawy_original_html_invalid",
    "masrawy_publisher_publication_date_unverified",
    "masrawy_rss_timestamp_invalid",
    "masrawy_rss_timestamp_unrecognized",
    "masrawy_rss_title_invalid",
})

def observe(*, limit: int = 6, read=read_feed, original=original_pubdate):
    if not 1 <= limit <= 8:
        raise ValueError("masrawy_qa_limit_out_of_bounds")
    cfg=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    matches=[f for f in cfg["feeds"] if f["id"]=="masrawy"]
    if len(matches)!=1:
        raise RuntimeError("masrawy_approved_feed_identity_hold")
    raw=read(matches[0]["url"],cfg["max_feed_bytes"])
    root=ET.fromstring(raw)
    if root.tag.rsplit("}",1)[-1]!="rss":
        raise RuntimeError("masrawy_original_feed_not_rss")
    items=root.findall("./channel/item")[:limit]
    outcome=Counter()
    for entry in items:
        url=(entry.findtext("link") or "").strip()
        title=(entry.findtext("title") or "").strip()
        date=(entry.findtext("pubDate") or "").strip()
        try:
            stamp,_=original(url,title,date)
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("masrawy_publisher_publication_date_unverified")
            outcome["verified_original_publication_time"]+=1
        except Exception as error:
            code=str(error) if type(error) in (ValueError,RuntimeError) else ""
            label=code if code in KNOWN_HOLD else (
                type(error).__name__ if type(error).__name__ in
                ("HTTPError","URLError","TimeoutError") else "other")
            outcome[label]+=1
    return {
        "mode":"RASD_MASRAWY_ORIGINAL_PUBLICATION_QA_NO_SEND",
        "sampled_original_articles":len(items),
        "outcomes":dict(sorted(outcome.items())),
        "original_timestamp_requirement":"explicit_timezone_exact_original_title_same_wall_clock",
        "rss_feed_changes":0,"sources_activated":0,
        "images_claimed":0,"emails_sent":0,
    }

def main():
    print(json.dumps(observe(),ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
