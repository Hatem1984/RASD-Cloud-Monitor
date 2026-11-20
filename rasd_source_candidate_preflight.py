"""Read-only qualification of up to 100 reviewed RASD research origins.

This does NOT activate feeds, capture genuine screenshots, write archives,
read private credentials or send email. An RSS success is only a candidate
for separate original-page/date/screenshot QA, never a production success.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener
from xml.etree.ElementTree import ParseError

from monitor import RejectRedirect, parse_rss
from rasd_candidate_atom import parse_first_party_atom
from research_source_queries_100 import load_100_sources

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 1_500_000
MAX_HOME_BYTES = 400_000
MAX_CANDIDATE_FETCHES = 6
_TIMEOUT = 7

# Publisher's own RSS listing exposes these section paths; research ONLY.
# Not added to sources_newsroom_active.json and NEVER an approved feed.
KNOWN_FIRST_PARTY_RESEARCH_FEEDS = {
    "youm7": (
        "https://www.youm7.com/rss/SectionRss?SectionID=297",
        "https://m.youm7.com/rss/SectionRss?SectionID=297",
    ),
}


def same_publisher(url: str, host: str) -> bool:
    """Keep every request first-party HTTPS, without credentials or odd ports."""
    try:
        if (not isinstance(host, str) or
                host.endswith((".local", ".localhost", ".internal", ".test", ".invalid"))):
            return False
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return False
        p = urlsplit(url)
        return bool(
            re.fullmatch(r"[a-z0-9.-]{4,180}", host)
            and host.count(".") >= 1
            and p.scheme == "https" and p.hostname in {host, "www." + host, "m." + host}
            and p.port in (None, 443)
            and not p.username and not p.password
            and not p.fragment and len(url) <= 1600
        )
    except (ValueError, TypeError, AttributeError):
        return False


class Alternates(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "link":
            return
        data = dict(attrs)
        rel = (data.get("rel") or "").lower().split()
        mime = (data.get("type") or "").lower()
        if "alternate" in rel and mime in {
                "application/rss+xml", "application/atom+xml",
                "application/rdf+xml"} and data.get("href"):
            self.links.append(data["href"])


def feed_candidates(homepage: str, publisher_host: str, html: bytes) -> list[str]:
    candidates = []
    parser = Alternates()
    try:
        parser.feed(html.decode("utf-8", errors="replace"))
    except (ValueError, TypeError):
        pass
    for href in parser.links[:12]:
        url = urljoin(homepage, href)
        if same_publisher(url, publisher_host) and url not in candidates:
            candidates.append(url)
    parsed = urlsplit(homepage)
    origin = parsed.scheme + "://" + parsed.netloc
    for suffix in ("/feed/", "/rss.xml", "/rss/"):
        url = origin + suffix
        if same_publisher(url, publisher_host) and url not in candidates:
            candidates.append(url)
    return candidates[:MAX_CANDIDATE_FETCHES - 1]


def _fetch(url: str, max_bytes: int) -> bytes:
    """Strict TLS, bounded GET, no redirects (including cross-host)."""
    opener = build_opener(RejectRedirect)
    request = Request(url, headers={
        "User-Agent": "RASD-Source-Research/1.0 (no-mail)",
        "Accept": "application/rss+xml, application/xml, text/xml, text/html",
    })
    with opener.open(request, timeout=_TIMEOUT) as response:
        if response.status != 200:
            raise ValueError("upstream_not_ok")
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes or not payload.strip():
        raise ValueError("source_body_invalid_or_too_large")
    return payload


def _failure_class(exc: Exception, payload: bytes = b"") -> str:
    """Deliberately finite public reason codes; no URLs, bodies or exceptions."""
    if isinstance(exc, HTTPError):
        if exc.code in (301, 302, 303, 307, 308):
            return "PUBLISHER_REDIRECT_HOLD"
        if exc.code in (401, 403, 429):
            return "PUBLISHER_REFUSED_OR_RATE_LIMITED"
        if exc.code in (404, 410):
            return "RSS_ENDPOINT_NOT_FOUND"
        return "PUBLISHER_HTTP_ERROR"
    if isinstance(exc, (URLError, TimeoutError, OSError)):
        return "NETWORK_OR_TLS_UNAVAILABLE"
    if isinstance(exc, ParseError):
        return "MALFORMED_XML"
    if isinstance(exc, ValueError):
        value = str(exc)
        if value in {"not_rss", "not_atom"}:
            if payload.lstrip()[:150].lower().startswith(
                    (b"<!doctype html", b"<html")):
                return "HTML_NOT_RSS_OR_ATOM"
            return "UNSUPPORTED_FEED_FORMAT"
        if ("date" in value or "identity" in value or "entry" in value or
                "duplicate" in value or "conflict" in value):
            return "ORIGINAL_ITEM_IDENTITY_OR_DATE_HOLD"
        if value in {"DTD_or_entity_forbidden", "atom_unsafe_xml"}:
            return "UNSAFE_XML"
    return "OTHER_RESEARCH_HOLD"


def inspect_candidate(row: dict, active: dict, keywords: list[str],
                      now: datetime, *, fetch=_fetch) -> dict:
    """Check one publisher independently; never count a link as a verified photo."""
    ident = row["id"]
    host = row["publisher_host"]
    homepage = row["homepage_url"]
    outcome = {"id": ident, "stage": "HOLD", "rss_items": 0,
               "matched_recent_items": 0, "matched_previous_complete_hour": 0,
               "matched_last_24_hours": 0, "hold_reason": "NO_NATIVE_FEED_CONFIRMED",
               "feed_endpoint_candidates_checked": 0,
               "production_approved": ident in active}
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("candidate_clock_needs_timezone")
    if not same_publisher(homepage, host):
        outcome["hold_reason"] = "UNSAFE_PUBLISHER_ORIGIN"
        return outcome
    failures = []
    if ident in active:
        endpoints = [active[ident]["url"]]
    else:
        try:
            homepage_html = fetch(homepage, MAX_HOME_BYTES)
        except (HTTPError, URLError, OSError, TimeoutError, RuntimeError, ValueError) as exc:
            failures.append("HOMEPAGE_" + _failure_class(exc))
            homepage_html = b""
        endpoints = list(KNOWN_FIRST_PARTY_RESEARCH_FEEDS.get(ident, ()))
        for candidate in feed_candidates(homepage, host, homepage_html):
            if candidate not in endpoints:
                endpoints.append(candidate)
    for endpoint in endpoints[:MAX_CANDIDATE_FETCHES]:
        if not same_publisher(endpoint, host):
            failures.append("UNSAFE_CROSS_ORIGIN_FEED")
            continue
        outcome["feed_endpoint_candidates_checked"] += 1
        data = b""
        try:
            data = fetch(endpoint, MAX_BYTES)
            reviewed_feed = {"id": ident, "name": row["name_ar"],
                             "allowed_article_hosts": [
                                 host, "www." + host, "m." + host]}
            # Distinguish formats for research. Production parser remains
            # its separately approved strict original RSS implementation.
            if data.lstrip().startswith(b"<?xml") or data.lstrip().startswith(b"<"):
                from xml.etree import ElementTree as ET
                if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                    raise ValueError("DTD_or_entity_forbidden")
                root_tag = ET.fromstring(data).tag.rsplit("}", 1)[-1]
            else:
                raise ValueError("not_rss")
            if root_tag == "rss":
                count, matched = parse_rss(
                    data, reviewed_feed, keywords, now=now,
                    recent_hours=72, require_complete_items=True)
                native_kind = "RSS"
            elif root_tag == "feed":
                count, matched = parse_first_party_atom(
                    data, reviewed_feed, keywords, now=now, recent_hours=72)
                native_kind = "ATOM"
            else:
                raise ValueError("not_rss")
            if count <= 0:
                failures.append("NATIVE_FEED_ZERO_COMPLETE_ITEMS")
                continue
        except (HTTPError, URLError, OSError, TimeoutError, ParseError,
                RuntimeError, ValueError, TypeError, AttributeError) as exc:
            failures.append(_failure_class(exc, data))
            continue
        outcome["rss_items"] = count
        outcome["matched_recent_items"] = len(matched)
        outcome["native_feed_format"] = native_kind
        checked = now.astimezone(timezone.utc)
        completed_hour_end = checked.replace(minute=0, second=0, microsecond=0)
        completed_hour_start = completed_hour_end - timedelta(hours=1)
        for article in matched:
            # Dates are timezone-aware original RSS / Atom <published>, not
            # fetch time; still NOT an original-page screenshot.
            stamp = parsedate_to_datetime(article["published"]).astimezone(timezone.utc)
            if completed_hour_start <= stamp < completed_hour_end:
                outcome["matched_previous_complete_hour"] += 1
            if checked - timedelta(hours=24) <= stamp <= checked:
                outcome["matched_last_24_hours"] += 1
        outcome["stage"] = (
            f"{native_kind}_MATCH_PENDING_ORIGINAL_PAGE_IMAGE_QA" if matched
            else f"{native_kind}_VALID_NO_RECENT_MINISTRY_MATCH")
        outcome.pop("hold_reason", None)
        break
    if outcome["stage"] == "HOLD":
        # Reasons are diagnostic; avoid implying the publisher itself is
        # permanently broken if the crawler did not find the correct path.
        priority = ("ORIGINAL_ITEM_IDENTITY_OR_DATE_HOLD", "UNSAFE_XML",
                    "MALFORMED_XML", "PUBLISHER_REFUSED_OR_RATE_LIMITED",
                    "PUBLISHER_REDIRECT_HOLD", "HTML_NOT_RSS_OR_ATOM",
                    "UNSUPPORTED_FEED_FORMAT", "NETWORK_OR_TLS_UNAVAILABLE",
                    "RSS_ENDPOINT_NOT_FOUND")
        outcome["hold_reason"] = next((reason for reason in priority
                                       if reason in failures),
                                      "NO_NATIVE_FEED_CONFIRMED")
    return outcome


def audit_catalog(*, limit: int, live: bool = False, fetch=_fetch,
                  workers: int = 5, now: datetime | None = None) -> dict:
    """Bounded 100-origin research only; no autoactivation or schedule."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("candidate_limit_out_of_scope")
    if type(workers) is not int or not 1 <= workers <= 6:
        raise ValueError("candidate_workers_out_of_scope")
    catalog = load_100_sources()
    config = json.loads((ROOT / "sources_newsroom_active.json").read_text(
        encoding="utf-8"))
    active = {row["id"]: row for row in config["feeds"]}
    rows = catalog["sources"][:limit]
    if not live:
        results = [{"id": row["id"], "stage": "NOT_CHECKED_OFFLINE",
                    "production_approved": row["id"] in active}
                   for row in rows]
    else:
        when = now or datetime.now(timezone.utc)
        if when.tzinfo is None or when.utcoffset() is None:
            raise ValueError("candidate_clock_needs_timezone")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(
                lambda row: inspect_candidate(
                    row, active, config["keywords"], when, fetch=fetch),
                rows))
    stages = {}
    hold_reasons = {}
    for result in results:
        stages[result["stage"]] = stages.get(result["stage"], 0) + 1
        if result["stage"] == "HOLD":
            reason = result.get("hold_reason", "UNKNOWN_HOLD")
            hold_reasons[reason] = hold_reasons.get(reason, 0) + 1
    previous_hour_rss = sum(row.get("matched_previous_complete_hour", 0)
                            for row in results)
    return {
        "scope": "RESEARCH_ONLY_NEVER_AUTOMATIC_SOURCE_APPROVAL",
        "sources_in_catalog": catalog["total_research_origins"],
        "sources_checked_or_listed": limit, "live_checked": live,
        "approved_production_inventory_unchanged": len(active),
        "screenshot_verified_by_this_audit": 0,
        "previous_complete_hour_rss_matches_not_approved_news": previous_hour_rss,
        "previous_complete_hour_6_to_7_original_photo_news_proven": False,
        "production_mail_sent": False, "schedule_changed": False,
        "status_counts": stages, "hold_reason_counts": hold_reasons,
        "sources": results,
    }


def main():
    parser = argparse.ArgumentParser(description="RASD source qualification; NO SEND")
    parser.add_argument("--live", action="store_true", help="Read public original sites only")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(audit_catalog(
        limit=args.limit, live=args.live, workers=args.workers),
        ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
