"""Strict first-party Youm7 Ministry tag discovery (RESEARCH ONLY, NO SMTP).

Tag index is owned by Youm7; it is only a discovery aid. Each accepted news
article MUST independently have an exact publisher HTML H1, approved planning
phrase in that H1, and explicit timezone-aware article:published_time.
Do not repair publisher dates, bypass anti-bot/refusal or accept search snippets.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from monitor import RejectRedirect, _ministry_term_present, article_id
from rasd_almal_original_html_research import PublisherPage

TAG_URL = ("https://www.youm7.com/Tags/Index?id=33679&tag="
           "%D9%88%D8%B2%D8%A7%D8%B1%D8%A9-%D8%A7%D9%84%D8%AA%D8%AE%D8%B7%D9%8A%D8%B7")
HOST="www.youm7.com"
NEWS_PATH=re.compile(r"^/story/\d{4}/\d{1,2}/\d{1,2}/[^/]+/\d{5,10}$")
MAX_INDEX_BYTES=750_000
MAX_PAGE_BYTES=850_000


def allowed(url: str) -> bool:
    try:
        p=urlsplit(url)
        return (p.scheme=="https" and p.hostname==HOST
                and p.port in (None,443)
                and not p.username and not p.password
                and not p.fragment and len(url)<=2200)
    except (ValueError,TypeError,AttributeError):
        return False


def fetch(url: str, limit: int) -> bytes:
    if not allowed(url) or limit not in {MAX_INDEX_BYTES,MAX_PAGE_BYTES}:
        raise ValueError("youm7_original_url_invalid")
    req=Request(url,headers={"User-Agent":"RASD-Publisher-Origin-Research/1.0",
                             "Accept":"text/html"})
    with build_opener(RejectRedirect()).open(req,timeout=12) as response:
        if response.status!=200 or response.geturl()!=url:
            raise ValueError("youm7_original_response_invalid")
        data=response.read(limit+1)
    if not data or len(data)>limit:
        raise ValueError("youm7_original_html_size_hold")
    return data


def discover_links(index: bytes, keywords: list[str],*,limit: int=20) -> list[str]:
    if not isinstance(index,bytes) or len(index)>MAX_INDEX_BYTES or not 1<=limit<=25:
        raise ValueError("youm7_index_unverifiable")
    page=PublisherPage()
    page.feed(index.decode("utf-8","replace"))
    urls=[]
    for relative,anchor in page.anchors:
        raw=urljoin(TAG_URL,html.unescape(relative or ""))
        parsed=urlsplit(raw)
        url=urlunsplit((parsed.scheme,parsed.netloc,
                        quote(parsed.path,safe="/%"),parsed.query,parsed.fragment))
        if (allowed(url) and NEWS_PATH.fullmatch(urlsplit(url).path) and
                _ministry_term_present(anchor,keywords) and url not in urls):
            urls.append(url)
    return urls[:limit]


def original_news(url: str, article: bytes, keywords: list[str],
                  *,now: datetime) -> dict:
    if not allowed(url) or not NEWS_PATH.fullmatch(urlsplit(url).path):
        raise ValueError("youm7_article_origin_invalid")
    if not isinstance(article,bytes) or not 1<=len(article)<=MAX_PAGE_BYTES:
        raise ValueError("youm7_article_html_invalid")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("youm7_original_clock_invalid")
    parser=PublisherPage()
    parser.feed(article.decode("utf-8","replace"))
    title=" ".join(" ".join(parser.headline).split())
    if not (15<=len(title)<=450 and _ministry_term_present(title,keywords)):
        raise ValueError("youm7_original_headline_unrelated")
    if len(parser.published)!=1:
        raise ValueError("youm7_original_publication_not_unique")
    try:
        instant=datetime.fromisoformat(parser.published[0].replace("Z","+00:00"))
    except (ValueError,TypeError,OverflowError):
        raise ValueError("youm7_original_publication_invalid") from None
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("youm7_original_publication_timezone_missing")
    utc=instant.astimezone(timezone.utc)
    if not now.astimezone(timezone.utc)-timedelta(hours=72)<=utc<=now.astimezone(timezone.utc):
        raise ValueError("youm7_original_news_outside_72h")
    return {"id":article_id(url),"headline":title,"url":url,
            "source":"Youm7 first-party Ministry tag HTML",
            "published":format_datetime(instant),"publisher_excerpt":"",
            "match_origin":"publisher_original_article_title"}


def research(*, now: datetime, downloader=fetch, keywords: list[str]|None=None) -> dict:
    if keywords is None:
        import json
        from pathlib import Path
        keywords=json.loads(Path("sources_newsroom_active.json").read_text(
            encoding="utf-8"))["keywords"]
    index=downloader(TAG_URL,MAX_INDEX_BYTES)
    urls=discover_links(index,keywords)
    stories=[]
    holds=0
    for url in urls:
        try:
            result=original_news(url,downloader(url,MAX_PAGE_BYTES),keywords,now=now)
            stories.append(result)
        except (OSError,TimeoutError,ValueError,RuntimeError):
            holds+=1
    return {"ministry_tag_first_party_links":len(urls),
            "original_pages_dated":len(stories),
            "original_page_hold":holds,"stories":stories,
            "production_activated":False,"smtp_sent":False}


def main():
    result=research(now=datetime.now(timezone.utc))
    print("RASD_YOUM7_TAG_LINKS="+str(result["ministry_tag_first_party_links"]))
    print("RASD_YOUM7_ORIGINAL_PAGES_DATED="+str(result["original_pages_dated"]))
    print("RASD_YOUM7_ORIGINAL_HOLD="+str(result["original_page_hold"]))
    print("RASD_YOUM7_NO_SEND_NO_ACTIVATION=1")


if __name__=="__main__":
    main()
