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
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener
from xml.etree.ElementTree import ParseError

from monitor import RejectRedirect, parse_rss
from research_source_queries_100 import load_100_sources

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 1_500_000
MAX_HOME_BYTES = 400_000
MAX_CANDIDATE_FETCHES = 4
_TIMEOUT = 7


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
            and p.scheme == "https" and p.hostname in {host, "www." + host}
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


def inspect_candidate(row: dict, active: dict, keywords: list[str],
                      now: datetime, *, fetch=_fetch) -> dict:
    """Check one publisher independently; no result authorizes production."""
    ident = row["id"]
    host = row["publisher_host"]
    homepage = row["homepage_url"]
    outcome = {"id": ident, "stage": "HOLD", "rss_items": 0,
               "matched_recent_items": 0, "production_approved": ident in active}
    if not same_publisher(homepage, host):
        return outcome
    if ident in active:
        endpoints = [active[ident]["url"]]
    else:
        try:
            homepage_html = fetch(homepage, MAX_HOME_BYTES)
        except (HTTPError, URLError, OSError, TimeoutError, RuntimeError, ValueError):
            homepage_html = b""
        endpoints = feed_candidates(homepage, host, homepage_html)
    for endpoint in endpoints:
        if not same_publisher(endpoint, host):
            continue
        try:
            data = fetch(endpoint, MAX_BYTES)
            reviewed_feed = {"id": ident, "name": row["name_ar"],
                             "allowed_article_hosts": [host, "www." + host]}
            count, matched = parse_rss(
                data, reviewed_feed, keywords, now=now,
                recent_hours=72, require_complete_items=True)
            if count <= 0:
                continue
        except (HTTPError, URLError, OSError, TimeoutError, ParseError,
                RuntimeError, ValueError, TypeError, AttributeError):
            continue
        outcome["rss_items"] = count
        outcome["matched_recent_items"] = len(matched)
        outcome["stage"] = ("RSS_MATCH_PENDING_ORIGINAL_PAGE_IMAGE_QA"
                            if matched else "RSS_VALID_NO_RECENT_MINISTRY_MATCH")
        break
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
    for result in results:
        stages[result["stage"]] = stages.get(result["stage"], 0) + 1
    return {
        "scope": "RESEARCH_ONLY_NEVER_AUTOMATIC_SOURCE_APPROVAL",
        "sources_in_catalog": catalog["total_research_origins"],
        "sources_checked_or_listed": limit, "live_checked": live,
        "approved_production_inventory_unchanged": len(active),
        "screenshot_verified_by_this_audit": 0,
        "production_mail_sent": False, "schedule_changed": False,
        "status_counts": stages, "sources": results,
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
