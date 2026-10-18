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
import unicodedata
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import sleep
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


# Keep saved Ministry phrases unchanged. Normalize native RSS TYPOGRAPHY only
# for matching: Arabic diacritics/tatweel and common Alef variants. Do not
# introduce broad 'اقتصاد' or 'تنمية' keywords on the owner's behalf.
_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]")
_ARABIC_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})
_DC_DATE = "{http://purl.org/dc/elements/1.1/}date"


def _native_text(raw: str) -> str:
    """Strip publisher RSS HTML tags and entities; no HTML becomes evidence."""
    value = html.unescape(raw)
    value = re.sub(r"<[^>]*>", " ", value)
    return " ".join(value.split())


def _matchable_arabic(value: str) -> str:
    value = unicodedata.normalize("NFKC", _native_text(value))
    value = _ARABIC_DIACRITICS.sub("", value).translate(_ARABIC_ALEF)
    return " ".join(value.casefold().split())


def _ministry_term_present(value: str, saved_keywords: list[str]) -> bool:
    text = _matchable_arabic(value)
    return any(
        bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))
        for keyword in saved_keywords if (phrase := _matchable_arabic(keyword))
    )


def _publisher_timestamp(node) -> tuple[datetime, str] | None:
    """Never invent timezone or treat RSS fetch time as publication time.

    Prefer publisher-owned RSS pubDate; support a standards-based Dublin
    Core dc:date only when pubDate is completely absent. If a supplied
    pubDate is malformed, refuse instead of silently switching identities.
    """
    original = (node.findtext("pubDate") or "").strip()
    if original:
        try:
            timestamp = parsedate_to_datetime(original)
        except (ValueError, TypeError, OverflowError, IndexError):
            return None
        if timestamp is None or timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return None
        return timestamp, original
    dc = (node.findtext(_DC_DATE) or "").strip()
    if not dc:
        return None
    try:
        timestamp = datetime.fromisoformat(dc.replace("Z", "+00:00"))
    except (ValueError, TypeError, OverflowError):
        return None
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return None
    return timestamp, format_datetime(timestamp)


def parse_rss(data: bytes, feed: dict, keywords: list[str], now=None, recent_hours=72) -> tuple[int, list[dict]]:
    """Match saved Ministry phrases in native publisher title OR excerpt.

    RSS is a bounded CURRENT feed, not a full publisher archive. Only
    explicitly timezone-aware publication dates may become report stories.
    """
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("DTD_or_entity_forbidden")
    root = ET.fromstring(data)
    if root.tag.rsplit("}", 1)[-1] != "rss":
        raise ValueError("not_rss")
    now = datetime.now(timezone.utc) if now is None else now
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("naive_monitor_clock_forbidden")
    now = now.astimezone(timezone.utc)
    eligible, matched, ids = 0, [], set()
    for node in root.findall("./channel/item"):
        title = (node.findtext("title") or "").strip()[:300]
        url = (node.findtext("link") or "").strip()
        if not title or not is_publisher_link(url, feed["allowed_article_hosts"]):
            continue
        eligible += 1
        # Publisher-owned description may contain a saved phrase absent in
        # the headline. It is never substituted for a source-page screenshot.
        description = _native_text((node.findtext("description") or "")[:3500])[:850]
        title_match = _ministry_term_present(title, keywords)
        description_match = _ministry_term_present(description, keywords)
        if not title_match and not description_match:
            continue
        dated = _publisher_timestamp(node)
        if dated is None:
            continue
        timestamp, published = dated
        if not (now - timedelta(hours=recent_hours) <= timestamp.astimezone(timezone.utc)
                <= now + timedelta(minutes=30)):
            continue
        item_id = article_id(url)
        if item_id in ids:
            continue
        ids.add(item_id)
        matched.append({
            "id": item_id, "source": feed["name"],
            "headline": title, "url": url, "published": published,
            "publisher_excerpt": description,
            "match_origin": "title" if title_match else "publisher_description",
        })
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
                  "verified_links": 0, "headline_matches": 0,
                  "description_matches": 0}
        for attempt in range(2):
            try:
                data = fetch(feed["url"], config["max_feed_bytes"])
                count, matches = parse_rss(data, feed, config["keywords"], checked,
                                           config["recent_hours"])
                record.update(
                    status="ok", verified_links=count,
                    headline_matches=len(matches),
                    description_matches=sum(
                        row.get("match_origin") == "publisher_description"
                        for row in matches),
                )
                record.pop("error", None)
                for entry in matches:
                    if entry["id"] not in ids:
                        discovered.append(entry)
                        ids.add(entry["id"])
                break
            except Exception as exc:
                # Report only bounded machine-readable diagnostics; never
                # propagate server body, URL parameters, or exception text.
                record["error"] = type(exc).__name__
                record["http_status"] = (
                    exc.code if isinstance(exc, HTTPError)
                    and exc.code in {301, 302, 303, 307, 308, 400, 401, 403, 404, 408, 429,
                                     500, 502, 503, 504}
                    else None
                )
                # One bounded retry only for transient upstream/network
                # errors. HTTP 429 is an explicit publisher rate-limit: DO NOT
                # retry and risk aggravating it. Respect 403, redirects, unsafe
                # endpoint and invalid publisher data by holding the source.
                transient = isinstance(exc, (ET.ParseError, TimeoutError, URLError))
                if isinstance(exc, HTTPError):
                    transient = exc.code in {500, 502, 503, 504}
                if not transient or attempt == 1:
                    break
                if isinstance(exc, ET.ParseError):
                    # The publisher sometimes serves malformed transient XML
                    # and immediately recovers. A rapid identical re-request
                    # can hit the same bad upstream response. Wait once;
                    # never repair publisher text, skip bad XML items, or
                    # claim the source healthy until a second FULL parse.
                    record["rss_parse_retry_delayed"] = True
                    sleep(1.25)
        sources.append(record)
    if not sources or all(item["status"] == "failed" for item in sources):
        raise RuntimeError("all_public_RSS_sources_failed")
    return {
        "kind": "manual_public_RSS_dry_run",
        "checked_at_utc": checked.isoformat(),
        "public_verified_publisher_links": sum(s["verified_links"] for s in sources),
        "planning_headline_matches": len(discovered),
        "native_description_matches": sum(
            row.get("match_origin") == "publisher_description"
            for row in discovered),
        "rss_feed_is_exhaustive_archive": False,
        "sources": sources,
        "matched_public_articles": discovered[:article_limit],
        "email_sent": False,
        "scheduler_enabled": False,
        "state_persistence_enabled": False,
        "limitations": ("Publisher-owned RSS title and short-description matching "
                        "against the exact saved Ministry of Planning terms. "
                        "RSS feeds expose a rolling/current inventory, NOT a complete "
                        "historical or whole-web archive. Date is the original "
                        "timezone-aware publisher timestamp, never fetch time. "
                        "Read-only scan does not persist cross-run deduplication."),
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
