"""Offline source and keyword configuration audit for MA'AL.

Never queries a publisher or a secret. A catalog entry is not a live feed,
and config success is not evidence of article/page/screenshot delivery.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


def source_coverage(research: dict, active: dict, candidates: dict) -> dict:
    """Strictly reconcile the three owner-reviewed configuration inputs."""
    sources = research.get("sources")
    feeds = active.get("feeds")
    keywords = active.get("keywords")
    suggestions = candidates.get("candidates")
    if not all(isinstance(group, list) for group in
               (sources, feeds, keywords, suggestions)):
        raise ValueError("invalid_source_inventory_structure")

    research_ids = [src.get("id") for src in sources if isinstance(src, dict)]
    active_ids = [src.get("id") for src in feeds if isinstance(src, dict)]
    if (len(research_ids) != len(sources) or
            len(active_ids) != len(feeds) or
            any(not isinstance(x, str) or not x.strip() for x in research_ids + active_ids)):
        raise ValueError("invalid_source_identifier")
    if len(set(research_ids)) != len(research_ids):
        raise ValueError("duplicate_research_id")
    if len(set(active_ids)) != len(active_ids):
        raise ValueError("duplicate_active_feed_id")
    if not set(active_ids).issubset(set(research_ids)):
        raise ValueError("active_feed_not_in_reviewed_catalog")

    for feed in feeds:
        url = feed.get("url")
        hosts = feed.get("allowed_article_hosts")
        if not isinstance(url, str) or not isinstance(hosts, list) or not hosts:
            raise ValueError("invalid_activated_feed_policy")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("active_feed_requires_trusted_https")
        if not all(isinstance(host, str) and host.strip() and
                   "://" not in host for host in hosts):
            raise ValueError("invalid_activated_article_hosts")

    if any(not isinstance(k, str) or not k.strip() for k in keywords):
        raise ValueError("invalid_monitored_keyword")
    normalized = [k.strip().casefold() for k in keywords]
    if len(set(normalized)) != len(normalized):
        raise ValueError("duplicate_monitored_keyword")

    statuses = []
    for candidate in suggestions:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("status"), str):
            raise ValueError("invalid_candidate_status")
        status = candidate["status"]
        ident = candidate.get("id")
        if not isinstance(ident, str) or not ident.strip():
            raise ValueError("invalid_candidate_identifier")
        if status.startswith("ACTIVATED_") and ident not in active_ids:
            raise ValueError("candidate_claims_activation_without_approved_feed")
        statuses.append(status)

    unactivated_ids = sorted(set(research_ids) - set(active_ids))
    return {
        "product": "MA'AL",
        "audit_type": "configuration_only_no_live_web_requests",
        "research_catalog_count": len(research_ids),
        "active_rss_feed_count": len(active_ids),
        "catalog_not_activated_count": len(unactivated_ids),
        "catalog_not_activated_ids": unactivated_ids,
        "keyword_count": len(keywords),
        "candidate_count": len(suggestions),
        "candidate_hold_count": sum(s.startswith("HOLD_") for s in statuses),
        "candidate_qa_only_count": sum(s.startswith("QA_ONLY_") for s in statuses),
        "candidate_activated_count": sum(s.startswith("ACTIVATED_") for s in statuses),
        "source_page_and_image_live_verified": False,
        "gmail_inbox_delivery_verified": False,
        "result": "CONFIG_RECONCILED_LIVE_ACCEPTANCE_REQUIRED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="MA'AL source readiness, offline")
    parser.add_argument("--research", default="research_sources_top50.json")
    parser.add_argument("--active", default="sources_newsroom_active.json")
    parser.add_argument("--candidates", default="sources_newsroom_expansion_candidates.json")
    options = parser.parse_args()

    def load(path: str) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    result = source_coverage(
        load(options.research), load(options.active), load(options.candidates))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
