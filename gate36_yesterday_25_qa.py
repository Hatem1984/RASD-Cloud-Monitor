"""Gate 36: isolated 25-story historical Cairo-day Word screenshot pilot.

This is an ephemeral QA experiment, not a production daily report, private
archive, email or schedule. It never uploads JPEGs or Word to a public repo.
If fewer than 25 eligible publisher RSS articles exist, HOLD (no final Word).
"""
from __future__ import annotations

import json
import tempfile
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from docx import Document

from capture_public import capture_publisher
from cloud_proof_report import proof_capture, word_images_match_capture_digests
from daily_report import CAIRO, cairo_display_time, render_docx
from gate11_runner import candidate_from_feed
from monitor import inspect, read_feed

TARGET_DAY = date(2026, 10, 17)
TARGET_COUNT = 25
APPROVED_PROFILE = ("hapi", "almasryalyoum")


def run_qa(*, config_path: Path = Path("sources.json"),
           now: datetime | None = None, fetch=read_feed,
           capture=capture_publisher, target_day: date = TARGET_DAY) -> dict:
    checked = datetime.now(timezone.utc) if now is None else now
    if checked.tzinfo is None or checked.utcoffset() is None:
        raise ValueError("gate36_naive_clock_forbidden")
    checked = checked.astimezone(timezone.utc)
    if type(target_day) is not date or checked.astimezone(CAIRO).date() != target_day + timedelta(days=1):
        raise ValueError("gate36_must_run_on_day_after_target")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    # No unilateral source expansion: the production two-source profile only.
    if tuple(feed["id"] for feed in config["feeds"]) != APPROVED_PROFILE:
        raise ValueError("gate36_approved_source_profile_required")
    scanned = inspect(config, fetch=fetch, now=checked, article_limit=200)
    source_health = [
        {"feed_id": s["feed_id"], "status": s["status"],
         "verified_links": s["verified_links"],
         "error_type": s.get("error") if s["status"] != "ok" else None}
        for s in scanned["sources"]
    ]
    coverage = "HEALTHY" if all(
        s["status"] == "ok" for s in source_health) else "DEGRADED"
    candidates = []
    for observed in scanned["matched_public_articles"]:
        valid = candidate_from_feed(observed, config, checked)
        if valid is None:
            continue
        stamp = parsedate_to_datetime(valid["published"]).astimezone(CAIRO)
        if stamp.date() == target_day:
            candidates.append((stamp, valid))
    candidates.sort(key=lambda item: item[0], reverse=True)
    available = len(candidates)
    chosen = candidates[:TARGET_COUNT]
    failures = Counter()
    successes = 0
    qa_word_verified = False
    start = datetime.combine(target_day, time.min, CAIRO)
    end = start + timedelta(days=1)  # [Cairo midnight, following midnight)
    with tempfile.TemporaryDirectory(prefix="rasd-qa25-") as directory:
        root = Path(directory)
        article_rows = []
        receipts = []
        for stamp, article in chosen:
            image_path = root / (article["id"] + ".jpg")
            evidence = proof_capture(
                article, config["feeds"], image_path, capture=capture)
            receipts.append(evidence)
            if evidence["status"] == "verified":
                successes += 1
            else:
                # proof_capture already restricts rejection codes.
                failures[evidence.get("reason", "other")] += 1
            article_rows.append({
                "id": article["id"],
                "headline": article["headline"],
                "publisher_excerpt": article.get("publisher_excerpt", ""),
                "source": article["source"],
                "url": article["url"],
                "published_at_cairo": stamp.strftime("%Y-%m-%d %H:%M %Z"),
                "published_display_cairo": cairo_display_time(stamp),
                **({"evidence_image_path": str(image_path)}
                   if evidence["status"] == "verified" else {}),
            })
        if (available >= TARGET_COUNT and len(chosen) == TARGET_COUNT and
                coverage == "HEALTHY" and successes == TARGET_COUNT):
            report = {
                "title": "رصد | اختبار ٢٥ خبرًا ليوم ١٧ أكتوبر — غير معتمد للنشر",
                "display_window_start": cairo_display_time(start),
                "display_window_end": cairo_display_time(end),
                "coverage": coverage,
                "verified_links": scanned["public_verified_publisher_links"],
                "articles": article_rows,
                "sources": source_health,
                "limitations": (
                    "اختبار معزول لـ٢٥ مادة صحفية من يوم ١٧ أكتوبر ٢٠٢٦ "
                    "بتوقيت القاهرة، مقتصر على مصادر RSS المعتمدة. "
                    "كل مادة لها لقطة حقيقية من صفحة الناشر؛ "
                    "لا يثبت ذلك أنها ٢٥ حدثًا مستقلًا أو تغطية شاملة. "
                    "هذه ليست نسخة الإنتاج ولا يجوز إرسالها تلقائيًا."
                ),
            }
            word = root / "RASD-QA25-2026-10-17.docx"
            render_docx(report, word)
            qa_word_verified = (
                word.is_file()
                and len(Document(word).inline_shapes) == TARGET_COUNT
                and word_images_match_capture_digests(word, receipts)
            )
    # No source URLs, headlines, image contents or private IDs in public logs.
    complete = (
        available >= TARGET_COUNT and coverage == "HEALTHY"
        and successes == TARGET_COUNT and qa_word_verified
    )
    return {
        "mode": "gate36_exact_previous_cairo_day_25_qa",
        "status": "READY_QA_ONLY" if complete else "HOLD",
        "target_date_cairo": target_day.isoformat(),
        "window_start_cairo": start.isoformat(),
        "window_end_exclusive_cairo": end.isoformat(),
        "target_articles": TARGET_COUNT,
        "eligible_articles_on_target_date": available,
        "selected_articles": len(chosen),
        "verified_original_page_images": successes,
        "missing_or_rejected_images": len(chosen) - successes,
        "rejection_reasons": dict(sorted(failures.items())),
        "coverage": coverage,
        "source_health": source_health,
        "word_bytes_verified_in_ephemeral_runner": qa_word_verified,
        "final_report_published": False,
        "public_document_or_images_uploaded": False,
        "email_sent": False,
        "scheduler_enabled": False,
        "private_storage_used": False,
        "production_article_limit_unchanged": True,
    }


def main() -> None:
    try:
        result = run_qa()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        if result["status"] == "HOLD":
            print("::warning::Gate36: 25-news original-publisher Word remains HOLD. "
                  "No final Word, public evidence, mail or schedule.", flush=True)
    except Exception:
        print("gate36_historical_pilot_failed_closed", flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
