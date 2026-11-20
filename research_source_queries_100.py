"""Offline 100-origin RASD research catalog. Does NOT monitor or authorize 100 feeds.

The first 50 entries are immutable legacy research records; the other 50
are new *candidate-only* newsroom/official/international origins. Use site:
queries as discovery hints, not as verified original article evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from research_source_queries import build_query, load_registry

EXTENSION = Path(__file__).resolve().parent / "research_sources_extension_50.json"
ACTIVE = Path(__file__).resolve().parent / "sources_newsroom_active.json"


def load_100_sources(extension: Path = EXTENSION) -> dict:
    original = load_registry()
    extra = json.loads(extension.read_text(encoding="utf-8"))
    rows = original["sources"] + extra["sources"]
    active = json.loads(ACTIVE.read_text(encoding="utf-8"))
    expected_active = {r["id"] for r in active["feeds"]}
    if (len(original["sources"]) != 50 or len(extra["sources"]) != 50 or
            len(rows) != 100 or
            [r["priority"] for r in rows] != list(range(1, 101)) or
            len({r["id"] for r in rows}) != 100 or
            len({r["homepage_url"] for r in rows}) != 100 or
            len(expected_active) != 14 or len(active["feeds"]) != 14):
        raise ValueError("rasd_catalog_100_integrity_hold")
    catalog_active = {
        r["id"] for r in rows if r["research_status"] == "active_native_rss"}
    if catalog_active != expected_active:
        raise ValueError("rasd_catalog_100_activation_disagreement")
    if any(r["research_status"] != "candidate_not_scheduled" or
           r["rss_status"] != "not_verified_no_feed_approved" or
           r["original_article_screenshot_status"] != "not_verified"
           for r in extra["sources"]):
        raise ValueError("rasd_catalog_100_candidate_autoactivation_forbidden")
    for row in rows:
        url = urlsplit(row["homepage_url"])
        host = row["publisher_host"]
        if (url.scheme != "https" or not url.hostname or
                url.hostname.removeprefix("www.") != host or
                url.username or url.password or url.fragment or
                not re.fullmatch(r"[a-z0-9.-]{4,180}", host) or
                not re.fullmatch(r"[a-z][a-z0-9_]{1,49}", row["id"])):
            raise ValueError("rasd_catalog_100_untrusted_origin")
    return {
        "schema_version": 1,
        "as_of": extra["as_of"],
        "total_research_origins": 100,
        "approved_automated_rss_sources": len(expected_active),
        "not_scheduled_research_candidates": 87,
        "sources": rows,
    }


def generate_100_queries(registry: dict, *, limit: int = 100,
                         official_only: bool = False) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("rasd_100_query_limit_invalid")
    rows = registry["sources"]
    if official_only:
        rows = [row for row in rows if row["category"] in
                ("official_primary", "official_primary_or_research",
                 "international_official_reference")]
    return [
        {
            "priority": row["priority"], "publisher": row["name_ar"],
            "origin": row["homepage_url"], "category": row["category"],
            "approved_automated_source":
                row["research_status"] == "active_native_rss",
            "research_status": row["research_status"],
            "query": build_query(row),
        }
        for row in rows[:limit]
    ]


def main() -> None:
    p = argparse.ArgumentParser(description="Print vetted-format 100 RASD research search hints; NO NETWORK/SMTP")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--official-only", action="store_true")
    args = p.parse_args()
    data = load_100_sources()
    print(json.dumps({
        "scope": "RESEARCH_QUERIES_NOT_100_AUTOMATED_SOURCES",
        "total_origins": 100, "automated_active": 13,
        "candidate_only": 87,
        "queries": generate_100_queries(data, limit=args.limit,
                                         official_only=args.official_only),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
