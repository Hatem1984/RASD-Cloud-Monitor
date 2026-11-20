"""Read-only publisher-specific original HTML article discovery: Al Mal.

RSS is not automatically available for every publisher. This parser only
accepts HTTPS first-party publisher home/article pages, exact original H1,
author-owned meta article:published_time with timezone, matching Ministry
phrases and original clickable article URL. No screenshot fabrication,
third-party search, Gmail, or production source activation.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener

from monitor import RejectRedirect, _ministry_term_present, article_id

ALMAL_ORIGIN = "https://almalnews.com/"
ALMAL_HOSTS = frozenset({"almalnews.com", "www.almalnews.com"})
ARTICLE_PATH = re.compile(r"^/[0-9]{5,9}(?:/|$)")
MAX_INDEX_BYTES = 550_000
MAX_PAGE_BYTES = 650_000


def permitted(url: str) -> bool:
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname in ALMAL_HOSTS
                and p.port in (None, 443) and p.username is None
                and p.password is None and not p.fragment and len(url) <= 1800)
    except (TypeError, ValueError, AttributeError):
        return False


def download(url: str, max_bytes: int) -> bytes:
    if not permitted(url) or max_bytes not in (MAX_INDEX_BYTES, MAX_PAGE_BYTES):
        raise ValueError("publisher_original_not_allowed")
    req = Request(url, headers={
        "User-Agent": "RASD-Original-Publisher-Research/1.0",
        "Accept": "text/html",
    })
    with build_opener(RejectRedirect()).open(req, timeout=12) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("publisher_page_not_original_response")
        data = response.read(max_bytes+1)
    if len(data) > max_bytes or not data:
        raise ValueError("publisher_html_unavailable_or_oversized")
    return data


class PublisherPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self.headline = []
        self.published = []
        self._a_href = None
        self._a_text = []
        self._in_h1 = 0

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "a":
            self._a_href = attrs.get("href")
            self._a_text = []
        elif tag == "h1":
            self._in_h1 += 1
        elif tag == "meta" and attrs.get("property") == "article:published_time":
            value = attrs.get("content")
            if value:
                self.published.append(value.strip())

    def handle_data(self, data):
        if self._a_href is not None:
            self._a_text.append(data)
        if self._in_h1:
            self.headline.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._a_href is not None:
            self.anchors.append((self._a_href, " ".join(
                " ".join(self._a_text).split())))
            self._a_href = None
            self._a_text = []
        elif tag == "h1" and self._in_h1:
            self._in_h1 -= 1


def candidate_links(homepage: bytes, keywords: list[str],
                    *, base: str = ALMAL_ORIGIN, limit: int = 16) -> list[str]:
    if type(limit) is not int or not 1 <= limit <= 20 or len(homepage) > MAX_INDEX_BYTES:
        raise ValueError("publisher_candidate_limit_invalid")
    page = PublisherPage()
    page.feed(homepage.decode("utf-8", "replace"))
    out = []
    for href, anchor in page.anchors:
        url = urljoin(base, html.unescape(href or ""))
        if (url not in out and permitted(url) and
                ARTICLE_PATH.match(urlsplit(url).path)
                and _ministry_term_present(anchor, keywords)):
            out.append(url)
    return out[:limit]


def original_story(url: str, data: bytes, keywords: list[str],
                   *, now: datetime, hours: int = 72) -> dict:
    if not permitted(url) or not ARTICLE_PATH.match(urlsplit(url).path):
        raise ValueError("publisher_article_url_invalid")
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_PAGE_BYTES:
        raise ValueError("publisher_article_bytes_invalid")
    if now.tzinfo is None or now.utcoffset() is None or hours != 72:
        raise ValueError("publisher_clock_invalid")
    page = PublisherPage()
    page.feed(data.decode("utf-8", "replace"))
    title = " ".join(" ".join(page.headline).split())
    if (not title or len(title) > 450 or
            not _ministry_term_present(title, keywords)):
        raise ValueError("publisher_original_headline_unrelated")
    if len(page.published) != 1:
        raise ValueError("publisher_published_meta_missing_or_ambiguous")
    try:
        when = datetime.fromisoformat(page.published[0].replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("publisher_published_meta_invalid") from None
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("publisher_published_timezone_missing")
    checked = now.astimezone(timezone.utc)
    if not checked - timedelta(hours=72) <= when.astimezone(timezone.utc) <= checked:
        raise ValueError("publisher_publication_outside_window")
    return {
        "id": article_id(url), "headline": title,
        "source": "Al Mal native publisher HTML",
        "url": url, "published": format_datetime(when),
        "publisher_excerpt": "", "match_origin": "original_page_headline",
    }


def research(*, now: datetime, fetch=download) -> dict:
    """Fresh original publisher index and 16-page max. Zero report/send."""
    from pathlib import Path
    import json
    cfg=json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    links=candidate_links(fetch(ALMAL_ORIGIN,MAX_INDEX_BYTES),cfg["keywords"])
    accepted = []
    held=0
    reasons={}
    for url in links:
        try:
            accepted.append(original_story(
                url,fetch(url,MAX_PAGE_BYTES),cfg["keywords"],now=now))
        except (OSError, TimeoutError, RuntimeError, ValueError) as error:
            held+=1
            from urllib.error import HTTPError, URLError
            if isinstance(error,HTTPError):
                reason="HTTP_"+str(error.code) if error.code in (401,403,404,410,429,500,502,503) else "HTTP_HOLD"
            elif isinstance(error,URLError):
                reason="NETWORK_HOLD"
            elif isinstance(error,ValueError) and str(error) in {
                "publisher_page_not_original_response",
                "publisher_published_meta_missing_or_ambiguous",
                "publisher_published_meta_invalid",
                "publisher_published_timezone_missing",
                "publisher_publication_outside_window",
                "publisher_original_headline_unrelated",
                "publisher_article_bytes_invalid",
                "publisher_html_unavailable_or_oversized",
                "publisher_article_url_invalid",
                "publisher_original_not_allowed",
            }:
                reason=str(error)
            elif isinstance(error,RuntimeError) and str(error)=="feed_redirect_blocked":
                reason="PUBLISHER_REDIRECT_HOLD"
            else:
                reason="UNVERIFIED_PUBLISHER_PAGE"
            reasons[reason]=reasons.get(reason,0)+1
    return {"index_candidates":len(links), "original_page_verified":len(accepted),
            "original_page_hold":held,"hold_reasons":reasons,"stories":accepted,
            "screenshot_verified_by_this_research":False,
            "production_activated":False,"smtp_sent":False}


if __name__=="__main__":
    summary=research(now=datetime.now(timezone.utc))
    print("RASD_ALMAL_HTML_INDEX_CANDIDATES="+str(summary["index_candidates"]))
    print("RASD_ALMAL_HTML_ORIGINAL_PAGES_DATED="+str(summary["original_page_verified"]))
    print("RASD_ALMAL_HTML_ORIGINAL_HOLD="+str(summary["original_page_hold"]))
    print("RASD_ALMAL_HTML_HOLD_REASONS="+str(summary["hold_reasons"]))
    print("RASD_ALMAL_HTML_NO_SEND_NO_ACTIVATION=1")
