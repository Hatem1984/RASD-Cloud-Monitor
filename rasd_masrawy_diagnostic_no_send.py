"""Bounded Masrawy original-source reliability diagnostics; never sends email.

Read one already approved original RSS feed, classify ALL publication timestamp
formats locally, and verify no more than eight real publisher pages: up to four
oldest and four newest. Publisher HTML and original article URLs/headlines
are never printed, saved, or uploaded.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from monitor import _ministry_term_present, read_feed
from masrawy_original_date import original_pubdate


SAFE_REASONS = frozenset({
    "masrawy_original_url_not_approved",
    "masrawy_original_page_redirect_forbidden",
    "masrawy_original_page_unavailable",
    "masrawy_original_page_size_hold",
    "masrawy_original_page_request_hold",
    "masrawy_original_html_invalid",
    "masrawy_publisher_publication_date_unverified",
    "masrawy_rss_timestamp_invalid",
    "masrawy_rss_timestamp_unrecognized",
    "masrawy_rss_title_invalid",
})


def sample_indices(count: int, *, max_checks: int = 8) -> list[int]:
    if type(count) is not int or count < 0 or not 0 <= max_checks <= 8:
        raise ValueError("rasd_masrawy_sample_size_invalid")
    head = list(range(min(4, count, max_checks)))
    tail = list(range(max(len(head), count - (max_checks - len(head))), count))
    return head + tail


def diagnose(config: dict, *, read=read_feed, original=original_pubdate,
             max_checks: int = 8) -> dict:
    feeds = [f for f in config["feeds"] if f.get("id") == "masrawy"]
    if len(feeds) != 1:
        raise ValueError("rasd_masrawy_active_feed_not_unique")
    feed = feeds[0]
    raw = read(feed["url"], config["max_feed_bytes"])
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("masrawy_rss_xml_entity_forbidden")
    root = ET.fromstring(raw)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("masrawy_feed_not_native_rss")
    items = root.findall("./channel/item")
    format_counts = Counter()
    matches = 0
    for node in items:
        date = (node.findtext("pubDate") or "").strip()
        try:
            parsed = datetime.strptime(date, "%m/%d/%Y %I:%M:%S %p")
        except ValueError:
            format_counts["nonstandard_or_missing"] += 1
        else:
            if parsed.tzinfo is None:
                format_counts["naive_masrawy_native"] += 1
            else:
                format_counts["explicit_timezone"] += 1
        title = (node.findtext("title") or "").strip()
        summary = (node.findtext("description") or "").strip()
        if _ministry_term_present(title + " " + summary, config["keywords"]):
            matches += 1
    sampled = Counter()
    index_failures = []
    for idx in sample_indices(len(items), max_checks=max_checks):
        node = items[idx]
        try:
            dt, published = original(
                (node.findtext("link") or "").strip(),
                (node.findtext("title") or "").strip(),
                (node.findtext("pubDate") or "").strip(),
            )
            if dt.tzinfo is None or dt.utcoffset() is None:
                raise ValueError("masrawy_publisher_publication_date_unverified")
            sampled["verified_original_page"] += 1
        except (RuntimeError, ValueError) as err:
            label = str(err) if str(err) in SAFE_REASONS else "unclassified_hold"
            sampled[label] += 1
            index_failures.append({"position": idx + 1, "reason": label})
        except Exception:
            sampled["unclassified_hold"] += 1
            index_failures.append({"position": idx + 1, "reason": "unclassified_hold"})
    return {
        "mode": "RASD_MASRAWY_ORIGINAL_RSS_DATE_DIAGNOSTIC_NO_SEND",
        "source_id": "masrawy",
        "total_rss_items": len(items),
        "publication_format_counts": dict(sorted(format_counts.items())),
        "ministry_phrase_matches_before_date_proof": matches,
        "sampled_original_pages": sum(sampled.values()),
        "sample_outcomes": dict(sorted(sampled.items())),
        "failure_positions": index_failures,
        "all_items_original_date_verified": (
            len(items) > 0 and max_checks >= len(items) and
            sampled["verified_original_page"] == len(items)),
        "no_send": True,
        "production_feed_unchanged": True,
        "inbox_delivery_verified": False,
    }


def main():
    cfg = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    result = diagnose(cfg)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
