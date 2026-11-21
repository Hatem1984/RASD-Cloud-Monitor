"""Offline planning utility for RASD's 50 ranked press/official research origins.

This DOES NOT fetch, search the web, activate sources, send emails, or touch
private data. It only prints publisher-restricted research queries for human
vetting while the production collector remains limited to fourteen approved RSS
profiles with first-party article verification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent / "research_sources_top50.json"
# The site operator is a discovery aid only: never treat search result snippets
# as the publisher's authenticated original article, timestamp or photograph.
QUERY_TERMS = (
    "وزارة التخطيط",
    "وزيرة التخطيط",
    "التخطيط والتنمية الاقتصادية",
    "المعهد القومي للتخطيط",
    "الخطة الاستثمارية للدولة",
    "السردية الوطنية للتنمية الاقتصادية",
)


def load_registry(path: Path = REGISTRY) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data["sources"]
    if len(sources) != 50 or sorted(s["priority"] for s in sources) != list(range(1, 51)):
        raise ValueError("research_registry_must_have_50_distinct_priorities")
    if len({s["id"] for s in sources}) != 50:
        raise ValueError("research_registry_duplicate_id")
    if len({s["homepage_url"] for s in sources}) != 50:
        raise ValueError("research_registry_duplicate_homepage")
    if sum(s["research_status"] == "active_native_rss" for s in sources) != 14:
        raise ValueError("research_registry_active_feeds_not_fourteen")
    return data


def build_query(source: dict) -> str:
    host = source["publisher_host"]
    if not host or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in host):
        raise ValueError("invalid_source_host")
    return "site:" + host + " (" + " OR ".join('"' + p + '"' for p in QUERY_TERMS) + ")"


def generate_queries(data: dict, *, official_only: bool = False, limit: int = 50) -> list[dict]:
    if not 1 <= limit <= 50:
        raise ValueError("invalid_query_limit")
    ranked = sorted(data["sources"], key=lambda x: x["priority"])
    if official_only:
        ranked = [s for s in ranked if s["category"] == "official_primary"]
    return [
        {"priority": s["priority"], "publisher": s["name_ar"], "publisher_origin": s["homepage_url"],
         "feed_operational": s["research_status"] == "active_native_rss", "query": build_query(s)}
        for s in ranked[:limit]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Print safe source-scoped research queries, no network")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--official-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(generate_queries(load_registry(), limit=args.limit,
                                      official_only=args.official_only),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
