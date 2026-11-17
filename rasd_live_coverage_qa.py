"""Read-only real-source coverage + original-page screenshot QA (NO SEND).

All 13 already approved RSS feeds are checked with the existing strict parser.
At most 3 qualifying original publisher pages are opened with the EXISTING
approved browser/screenshot guard. Verified JPEGs may be used in one TEMPORARY
QA-only Word to check exact image-to-article binding. Images and Word are
never uploaded, emailed or put into the public repository. Only bounded safe
source IDs/counts/fixed error codes are printed.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from cloud_proof_report import proof_capture, word_images_match_capture_digests
from daily_report import render_docx
from gate11_runner import SAFE_CAPTURE_FAILURE_CODES, candidate_from_feed
from monitor import inspect


def run_coverage_qa(config: dict, *, inspector=inspect, capture=proof_capture,
                    now: datetime | None = None, max_attempts: int = 3) -> dict:
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("timezone_required")
    if type(max_attempts) is not int or max_attempts not in (0, 1, 2, 3):
        raise ValueError("capture_qa_attempts_invalid")
    feeds = config.get("feeds")
    if not isinstance(feeds, list) or not feeds:
        raise ValueError("missing_approved_source_inventory")
    safe_ids = [f.get("id") for f in feeds]
    if (len(safe_ids) != len(set(safe_ids)) or
            any(not isinstance(fid, str) or
                    not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", fid)
                    for fid in safe_ids)):
        raise ValueError("unsafe_source_inventory_id")

    observation = inspector(config, now=checked_at, article_limit=200,
                            require_complete_items=True)
    source_rows = observation["sources"]
    if ([row["feed_id"] for row in source_rows] != safe_ids or
            any(row.get("status") not in ("ok", "failed")
                for row in source_rows)):
        raise RuntimeError("source_inventory_inconsistent")
    sources = [{
        "id": source["feed_id"],
        "status": source["status"],
        "links": min(10000, max(0, source.get("verified_links", 0))),
        "matches": min(10000, max(0, source.get("headline_matches", 0))),
        "error": (str(source.get("error", "")) if
                  str(source.get("error", "")) in
                  ("HTTPError", "URLError", "ParseError", "TimeoutError",
                   "ValueError", "RuntimeError", "ConnectionResetError",
                   "RemoteDisconnected") else "other")
        if source["status"] == "failed" else None,
        "http_status": (source.get("http_status")
                        if source.get("http_status") in
                        (301, 302, 303, 307, 308, 400, 401, 403, 404,
                         408, 429, 500, 502, 503, 504) else None),
        "xml_error_code": (source.get("xml_error_code")
                           if type(source.get("xml_error_code")) is int and
                           1 <= source["xml_error_code"] <= 99 else None),
        "safe_failure_code": (source.get("error_code")
                              if source.get("error_code") in (
                                  "feed_redirect_blocked",
                                  "feed_endpoint_not_reviewed",
                                  "feed_http_or_redirect_error",
                                  "rss_size_limit_exceeded",
                                  "DTD_or_entity_forbidden", "not_rss",
                                  "rss_channel_unverifiable",
                                  "rss_original_item_identity_unverifiable",
                                  "rss_original_item_date_unverifiable",
                                  "rss_original_duplicate_conflict",
                                  "other") else "other")
        if source["status"] == "failed" else None,
    } for source in source_rows]
    index = {f["name"]: f["id"] for f in feeds}
    qualified = []
    for row in observation["matched_public_articles"]:
        if row.get("source") not in index:
            continue
        try:
            item = candidate_from_feed(row, config, checked_at)
        except (ValueError, TypeError, KeyError):
            continue
        if item is not None:
            # The original feed date is already timezone-aware and validated
            # by the strict parser. Preserve that publisher date in this
            # temporary QA Word; never infer an unpublished hour.
            from email.utils import parsedate_to_datetime
            from zoneinfo import ZoneInfo
            stamp = parsedate_to_datetime(row["published"])
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                continue
            cairo = stamp.astimezone(ZoneInfo("Africa/Cairo"))
            item = {**item,
                    "published_at_cairo":
                    cairo.strftime("%Y-%m-%d %H:%M %Z")}
            qualified.append((index[row["source"]], item))
    counts = Counter(fid for fid, _ in qualified)
    receipts = []
    report_valid = False
    attempts = 0
    if max_attempts:
        with tempfile.TemporaryDirectory(prefix="rasd-real-qa-") as tmp:
            folder = Path(tmp)
            verified = []
            for fid, item in qualified:
                if attempts >= max_attempts:
                    break
                attempts += 1
                location = folder / f"source-{attempts:02d}.jpg"
                outcome = capture(item, feeds, location)
                reason = outcome.get("reason")
                verified_ok = (outcome.get("status") == "verified" and
                               isinstance(outcome.get("sha256"), str) and
                               len(outcome["sha256"]) == 64 and
                               location.is_file())
                receipts.append({
                    "source_id": fid,
                    "status": "verified" if verified_ok else "HOLD",
                    "reason": None if verified_ok else (
                        reason if reason in SAFE_CAPTURE_FAILURE_CODES
                        else "other"),
                })
                if verified_ok:
                    verified.append((
                        {**item, "evidence_image_path": str(location)},
                        {"status": "verified", "sha256": outcome["sha256"]},
                    ))
            if verified:
                articles = [row for row, _ in verified]
                evidence = [proof for _, proof in verified]
                report = {
                    "title": "رصد | تجربة تحقق المصدر والصورة — غير مخصص للإرسال",
                    "display_window_start": checked_at.isoformat(),
                    "display_window_end": checked_at.isoformat(),
                    "coverage": "SOURCE_LIMITED",
                    "verified_links": len(articles),
                    "articles": articles,
                    "sources": [],
                    "limitations": "عينة فنية محدودة من روابط أصلية؛ ليست تقرير اليوم.",
                    "scope_note": "اختبار حي دون إرسال أو نشر صور.",
                }
                word = folder / "original-image-QA-only.docx"
                render_docx(report, word)
                report_valid = word_images_match_capture_digests(word, evidence)
                if not report_valid:
                    raise RuntimeError("word_image_identity_hold")
    failures = sum(x["status"] == "failed" for x in sources)
    return {
        "mode": "RASD_LIVE_FIRST_PARTY_QA_NO_SEND",
        "status": ("DEGRADED_OR_PARTIAL" if failures else "SOURCES_REACHABLE_AT_CHECK"),
        "checked_sources": len(sources), "failed_sources": failures,
        "sources": sources,
        "qualified_keyword_candidates": len(qualified),
        "candidate_counts_by_source_id": dict(sorted(counts.items())),
        "capture_attempts": attempts,
        "capture_receipts": receipts,
        "verified_original_screenshots": sum(
            x["status"] == "verified" for x in receipts),
        "ephemeral_original_word_image_binding_verified": report_valid,
        "unverified_articles_not_delivered": True,
        "email_sent": False, "private_ledger_used": False,
        "scheduled_delivery_enabled": False,
        "new_production_sources_activated": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    config = json.loads(Path("sources_newsroom_active.json").read_text(
        encoding="utf-8"))
    result = run_coverage_qa(config, max_attempts=args.max_attempts)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    # This is a QA observation; degraded coverage is explicit, not a silent PASS.


if __name__ == "__main__":
    main()
