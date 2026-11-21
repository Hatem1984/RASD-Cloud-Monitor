"""Read-only first-party RSS candidate QA: no account, no SMTP, no archives.

This explicitly tests an exact, bounded set of publisher-owned endpoints and
does not add ANY source to production automatically. Publisher feed URLs must
return 200 with no redirect, native RSS with direct HTTPS first-party article
links and explicit timezone-aware publication dates. All errors are sanitized.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET

from monitor import RejectRedirect, parse_rss, safe_source_failure_code

MAX_BYTES=1_000_000
CANDIDATES=(
    {"id":"alnaharegypt","name":"Al Nahar Egypt native news RSS",
     "url":"https://www.alnaharegypt.com/feed/",
     "allowed_article_hosts":["www.alnaharegypt.com","alnaharegypt.com"],
     "kind":"egyptian_newsroom"},
    {"id":"businesstodayegypt","name":"Business Today Egypt native RSS",
     "url":"https://www.businesstodayegypt.com/feed/",
     "allowed_article_hosts":["www.businesstodayegypt.com","businesstodayegypt.com"],
     "kind":"egyptian_business"},
    {"id":"egypttoday","name":"Egypt Today native RSS",
     "url":"https://www.egypttoday.com/rss",
     "allowed_article_hosts":["www.egypttoday.com","egypttoday.com"],
     "kind":"egyptian_english"},
    {"id":"ahramonline","name":"Ahram Online Egypt RSS",
     "url":"https://english.ahram.org.eg/Portal/1/RSS.aspx",
     "allowed_article_hosts":["english.ahram.org.eg"],
     "kind":"egyptian_english"},
    {"id":"alwafd","name":"Al Wafd newspaper RSS",
     "url":"https://www.alwafd.news/rss",
     "allowed_article_hosts":["www.alwafd.news","alwafd.news"],
     "kind":"egyptian_newsroom"},
    {"id":"bbcarabic","name":"BBC Arabic native RSS",
     "url":"https://feeds.bbci.co.uk/arabic/rss.xml",
     "allowed_article_hosts":["www.bbc.com","www.bbc.co.uk","www.bbc.com"],
     "kind":"international_media"},
    {"id":"bbc_africa","name":"BBC News Africa native RSS",
     "url":"https://feeds.bbci.co.uk/news/world/africa/rss.xml",
     "allowed_article_hosts":["www.bbc.com","www.bbc.co.uk"],
     "kind":"international_media"},
    {"id":"unnews_ar","name":"UN News Arabic native RSS",
     "url":"https://news.un.org/feed/subscribe/ar/news/all/rss.xml",
     "allowed_article_hosts":["news.un.org"],
     "kind":"international_official"},
    {"id":"worldbank_blog","name":"World Bank original finance blog native RSS",
     "url":"https://blogs.worldbank.org/allaboutfinance/rss.xml",
     "allowed_article_hosts":["blogs.worldbank.org"],
     "kind":"international_official"},
)


def fetch_native(feed: dict) -> bytes:
    url=feed["url"]
    p=urlsplit(url)
    if (p.scheme!="https" or not p.hostname or p.username or p.password
            or p.port not in (None,443)):
        raise ValueError("candidate_not_https")
    request=Request(url,headers={"User-Agent":"RASD-first-party-source-qa/1.0",
                                 "Accept":"application/rss+xml,application/xml"})
    with build_opener(RejectRedirect()).open(request,timeout=14) as response:
        if response.status!=200 or response.geturl()!=url:
            raise ValueError("candidate_response_invalid")
        data=response.read(MAX_BYTES+1)
        if not data or len(data)>MAX_BYTES:
            raise ValueError("candidate_response_invalid")
        return data


def main():
    cfg=json.loads(open("sources_newsroom_active.json",encoding="utf-8").read())
    checked=datetime.now(timezone.utc)
    for candidate in CANDIDATES:
        result={"id":candidate["id"],"kind":candidate["kind"],"status":"HOLD",
                "rss_articles":0,"ministry_matches_72h":0,
                "sanitized_reason":"none"}
        try:
            doc=fetch_native(candidate)
            count,matches=parse_rss(
                doc,candidate,cfg["keywords"],now=checked,recent_hours=72,
                require_complete_items=True)
            result.update(status="RSS_DATE_LINK_PASS",
                          rss_articles=count,ministry_matches_72h=len(matches))
        except (HTTPError,URLError,OSError,TimeoutError,ValueError,RuntimeError,
                ET.ParseError) as error:
            code=safe_source_failure_code(error)
            result["sanitized_reason"]=code if code!="other" else type(error).__name__
        print("RASD_CANDIDATE_RSS_QA="+json.dumps(result,ensure_ascii=True),
              flush=True)
    print("RASD_CANDIDATE_QA_NO_ACTIVATION_NO_SMTP=1")

if __name__=="__main__":
    main()
