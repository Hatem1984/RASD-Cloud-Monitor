"""RASD Cloud Monitor — public RSS intake only.

No Gmail credentials, no automation schedule, no private RASD code or data.
The first deployment is an explicit manual dry-run: discoveries are public
publisher headlines and links, not full scraped articles.
"""
from __future__ import annotations

import hashlib
import html
import re
import json
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree as ET


# Reviewed, exact native publisher RSS endpoints; never accept arbitrary URLs
# from modified public configuration or follow redirects to other destinations.
APPROVED_FEED_URLS = frozenset({
    "https://hapijournal.com/feed/",
    "https://www.almasryalyoum.com/rss/rssfeeds",
    "https://www.shorouknews.com/Economy/rss",
})


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("feed_redirect_blocked")


def is_publisher_link(url: str, approved_hosts: list[str]) -> bool:
    try:
        value = urlsplit(url)
        return (value.scheme == "https"
                and value.hostname in approved_hosts
                and (value.port is None or value.port == 443)
                and not value.username and not value.password)
    except (ValueError, TypeError, AttributeError):
        return False


def canonical_url(url: str) -> str:
    value = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(value.query)
             if not k.lower().startswith("utm_")
             and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit(("https", value.netloc.lower(), value.path.rstrip("/") or "/",
                       urlencode(query), ""))


def article_id(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()[:24]


def parse_rss(data: bytes, feed: dict, keywords: list[str], now=None, recent_hours=72) -> tuple[int, list[dict]]:
    """Only process well-formed RSS with publisher-owned HTTPS article links."""
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("DTD_or_entity_forbidden")
    root = ET.fromstring(data)
    if root.tag.rsplit("}", 1)[-1] != "rss":
        raise ValueError("not_rss")
    now = datetime.now(timezone.utc) if now is None else now
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("naive_monitor_clock_forbidden")
    now = now.astimezone(timezone.utc)
    keywords = [x.casefold() for x in keywords if x.strip()]
    eligible, matched, ids = 0, [], set()
    for node in root.findall("./channel/item"):
        title = (node.findtext("title") or "").strip()[:300]
        url = (node.findtext("link") or "").strip()
        if not title or not is_publisher_link(url, feed["allowed_article_hosts"]):
            continue
        eligible += 1
        # Shorouk's native Economy RSS may mention the ministry only in its
        # short item description. This is still publisher-owned RSS text, not
        # aggregator discovery, and is used only for this reviewed feed.
        search_text = title
        if feed["id"] == "shorouk":
            raw_description = (node.findtext("description") or "")[:3500]
            short_description = html.unescape(re.sub(
                r"<[^>]*>", " ", raw_description))
            search_text += " " + short_description
        if not any(k in search_text.casefold() for k in keywords):
            continue
        published = (node.findtext("pubDate") or "").strip()
        if feed["id"] == "shorouk" and not published:
            continue  # No unverifiable timestamp for this newly admitted feed.
        if published:
            try:
                stamp = parsedate_to_datetime(published)
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                if not (now - timedelta(hours=recent_hours) <= stamp.astimezone(timezone.utc)
                        <= now + timedelta(hours=4)):
                    continue
            except (ValueError, TypeError, OverflowError):
                continue
        item_id = article_id(url)
        if item_id in ids:
            continue
        ids.add(item_id)
        matched.append({"id": item_id, "source": feed["name"],
                        "headline": title, "url": url, "published": published or None})
    return eligible, matched


def read_feed(url: str, size_limit: int) -> bytes:
    """Hardcoded, reviewed domain: never follow redirects or read unlimited content."""
    if url not in APPROVED_FEED_URLS:
        raise ValueError("feed_endpoint_not_reviewed")
    request = Request(url, headers={"User-Agent": "RASD-Cloud-Public-Monitor/0.1"})
    with build_opener(RejectRedirect()).open(request, timeout=20) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("feed_http_or_redirect_error")
        data = response.read(size_limit + 1)
        if len(data) > size_limit:
            raise ValueError("rss_size_limit_exceeded")
        return data


def inspect(config: dict, fetch=read_feed, now=None, *, article_limit: int = 15) -> dict:
    # The default preserves the original compact public monitoring response.
    # Reporting can explicitly request a larger validated pool before it sorts
    # by publisher publication time and selects the 15 newest headlines.
    if not isinstance(article_limit, int) or not 1 <= article_limit <= 200:
        raise ValueError("invalid_rss_article_limit")
    checked = datetime.now(timezone.utc) if now is None else now
    if checked.tzinfo is None or checked.utcoffset() is None:
        raise ValueError("naive_monitor_clock_forbidden")
    checked = checked.astimezone(timezone.utc)
    sources = []
    discovered = []
    ids = set()
    for feed in config["feeds"]:
        record = {"feed_id": feed["id"], "status": "failed",
                  "verified_links": 0, "headline_matches": 0}
        for attempt in range(2):
            try:
                data = fetch(feed["url"], config["max_feed_bytes"])
                count, matches = parse_rss(data, feed, config["keywords"], checked,
                                           config["recent_hours"])
                record.update(status="ok", verified_links=count,
                              headline_matches=len(matches))
                record.pop("error", None)
                for entry in matches:
                    if entry["id"] not in ids:
                        discovered.append(entry)
                        ids.add(entry["id"])
                break
            except Exception as exc:
                record["error"] = type(exc).__name__
                # One bounded reattempt for transient RSS/XML/network failure.
                # Never retry invalid publishers, unsafe redirects, DTD or
                # unapproved endpoints; never mask a second failure.
                transient = isinstance(exc, (ET.ParseError, TimeoutError, URLError))
                if isinstance(exc, HTTPError):
                    transient = exc.code in {429, 500, 502, 503, 504}
                if not transient or attempt == 1:
                    break
        sources.append(record)
    if not sources or all(item["status"] == "failed" for item in sources):
        raise RuntimeError("all_public_RSS_sources_failed")
    return {
        "kind": "manual_public_RSS_dry_run",
        "checked_at_utc": checked.isoformat(),
        "public_verified_publisher_links": sum(s["verified_links"] for s in sources),
        "planning_headline_matches": len(discovered),
        "sources": sources,
        "matched_public_articles": discovered[:article_limit],
        "email_sent": False,
        "scheduler_enabled": False,
        "state_persistence_enabled": False,
        "limitations": ("Native RSS headline-only monitoring of reviewed sources; "
                        "no comprehensive media coverage. This read-only scan "
                        "does not persist cross-run deduplication."),
    }


def main():
    settings = json.loads(Path("sources.json").read_text(encoding="utf-8"))
    result = inspect(settings)
    out = Path("evidence") / "latest-probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
