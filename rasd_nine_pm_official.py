"""Owner-authorized, single-date 21:00 Cairo ORIGINAL ministry-page Word pilot.

Not the 30-minute newsroom product: official press release from 21 Oct is
clearly marked historical/source-limited. No public artifacts, no insecure
source substitution, no mail outside the exact time and approved recipient.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from cloud_proof_report import word_images_match_capture_digests
from daily_report import CAIRO, render_docx
from official_ministry_source import (
    INDEX, _read_original, allowed_official_resource,
    discover_official_newslist, canonical_official_article)
from scheduled_rasd import (
    digest_key, protected_credentials, send_one_word)

PILOT_DAY = date(2026, 10, 22)
SOURCE_DAY = date(2026, 10, 21)
SOURCE_URL = "https://mped.gov.eg/singlenews?id=7272&lang=ar"
EXPECTED_WORKFLOW = (
    "Hatem1984/RASD-Cloud-Monitor/.github/workflows/"
    "rasd-nine-pm-official-oneoff.yml@refs/heads/main"
)
WORDS = [
    "وزارة التخطيط", "وزير التخطيط", "وزيرة التخطيط",
    "التخطيط والتنمية الاقتصادية",
]


def check_dispatch_clock(clock: datetime) -> None:
    """Reject retries, dispatch/push, other runs, dates and late launches."""
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise RuntimeError("untrusted_clock")
    cairo = clock.astimezone(CAIRO)
    if not (cairo.date() == PILOT_DAY and cairo.hour == 21 and cairo.minute <= 29):
        raise RuntimeError("single_date_nine_pm_window_expired")
    required = {
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_WORKFLOW_REF": EXPECTED_WORKFLOW,
        "GITHUB_RUN_ATTEMPT": "1",
    }
    if any(os.environ.get(key) != val for key, val in required.items()):
        raise RuntimeError("oneoff_schedule_not_authorized")
    if not os.environ.get("GITHUB_RUN_ID", "").isdigit():
        raise RuntimeError("invalid_run_identity")


def render_official_sample(output: Path, *, clock: datetime | None = None):
    """Original publisher NewsList discovery -> same original page -> real JPEG -> DOCX."""
    now = clock or datetime.now(timezone.utc)
    cfg = json.loads(Path("sources.json").read_text(encoding="utf-8"))
    if cfg.get("keywords") != WORDS or [f.get("id") for f in cfg.get("feeds", [])] != [
            "hapi", "almasryalyoum"]:
        raise RuntimeError("saved_ministry_profile_modified")
    if canonical_official_article(SOURCE_URL) != SOURCE_URL:
        raise RuntimeError("untrusted_official_article_url")
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = browser.new_context(
                viewport={"width": 1200, "height": 900}, locale="ar-EG",
                ignore_https_errors=False, accept_downloads=False,
                service_workers="block")
            context.route("**/*", lambda route: (
                route.continue_() if allowed_official_resource(route.request.url)
                else route.abort()))
            first = discover_official_newslist(context.request)
            second = discover_official_newslist(context.request)
            if SOURCE_URL not in first or SOURCE_URL not in second:
                raise RuntimeError("official_article_not_repeatably_discovered")
            result = _read_original(
                context.new_page(), SOURCE_URL, WORDS, SOURCE_DAY,
                output / "source-original.jpg")
            if result.get("status") != "verified":
                raise RuntimeError("official_publisher_original_capture_hold")
        finally:
            browser.close()
    report = {
        "title": "RASD | بروفة مصدر رسمي واحد — 9 مساءً 22 أكتوبر 2026",
        "display_window_start": "21 أكتوبر 2026 — تاريخ النشر الرسمي",
        "display_window_end": "22 أكتوبر 2026، 21:00 القاهرة — موعد البروفة",
        "coverage": "SOURCE_LIMITED_OFFICIAL_PILOT",
        "verified_links": 1,
        "articles": [{
            "headline": result["headline"],
            "source": "وزارة التخطيط والتنمية الاقتصادية — بيان رسمي",
            "url": result["url"],
            "published_at_cairo": "2026-10-21 — دون ساعة نشر موثقة",
            "published_display_cairo": "21 أكتوبر 2026 — تاريخ فقط",
            "evidence_image_path": result["image_path"],
        }],
        "sources": [{
            "feed_id": "mped-official", "status": "ok",
            "verified_links": 1, "error_type": None,
        }],
        "limitations": (
            "هذه بروفة لنقل تقرير Word حقيقي من بيان الوزارة المنشور يوم 21 أكتوبر،"
            " وليست تقرير أخبار يوم 22 أكتوبر ولا إثباتًا لتغطية الصحف"
            " أو تشغيل الفحص نصف الساعي. صورة الصفحة أصلية من موقع الوزارة."
        ),
    }
    path = output / "RASD-Official-Single-Source-Pilot-2026-10-22.docx"
    render_docx(report, path)
    if not word_images_match_capture_digests(
            path, [{"status": "verified", "sha256": result["sha256"]}]):
        path.unlink(missing_ok=True)
        raise RuntimeError("official_word_embedded_jpeg_digest_hold")
    if not 3000 <= path.stat().st_size <= 8_000_000:
        path.unlink(missing_ok=True)
        raise RuntimeError("official_word_size_hold")
    return path, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("proof", "send"), required=True)
    args = parser.parse_args()
    try:
        now = datetime.now(timezone.utc)
        if args.mode == "send":
            check_dispatch_clock(now)
        with tempfile.TemporaryDirectory(prefix="rasd-oneoff-official-") as temp:
            word, result = render_official_sample(Path(temp), clock=now)
            print("RASD_NINE_PM_ORIGINAL_MINISTRY_JPEG_AND_WORD=VERIFIED", flush=True)
            print("RASD_NINE_PM_ARTICLES=1 HISTORICAL_SOURCE_DAY=2026-10-21", flush=True)
            if args.mode == "proof":
                print("RASD_NINE_PM_PROOF_MODE=NO_EMAIL_NO_LEDGER", flush=True)
                return
            sender, recipient, password, ledger = protected_credentials()
            key = digest_key("owner-oneoff-20261022-official:" + result["id"])
            if ledger.reserve(key, recipient) != "reserved":
                print("RASD_NINE_PM_HOLD_ALREADY_RESERVED_OR_SENT", flush=True)
                raise SystemExit(2)
            print("RASD_NINE_PM_PRIVATE_CAS_RESERVED=PASS", flush=True)
            subject = "رصد | بروفة Word بمصدر رسمي واحد (21 أكتوبر) | 22 أكتوبر، 9 مساء"
            receipt = send_one_word(
                word, sender=sender, recipient=recipient, password=password,
                subject=subject, key=key)
            ledger.mark_smtp_accepted(key, receipt)
            print("RASD_NINE_PM_SMTP_ACCEPTED_PRIVATE_LEDGER=PASS", flush=True)
            print("RASD_NINE_PM_INBOX_CHECK=PENDING", flush=True)
    except SystemExit:
        raise
    except Exception as error:
        allowed = {
            "untrusted_clock", "single_date_nine_pm_window_expired",
            "oneoff_schedule_not_authorized", "invalid_run_identity",
            "saved_ministry_profile_modified", "untrusted_official_article_url",
            "official_article_not_repeatably_discovered",
            "official_publisher_original_capture_hold",
            "official_word_embedded_jpeg_digest_hold", "official_word_size_hold",
        }
        reason = str(error)
        print("RASD_NINE_PM_HOLD=" + (reason if reason in allowed else "unverified_or_private_error"), flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
