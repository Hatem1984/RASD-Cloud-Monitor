"""Original-page Ministry bulletin, independent of newsroom RSS.

Opt-in cloud-only daily official-source track. Original Ministry press releases
are NEVER relabeled as newspaper coverage. Chromium captures every included
page and SHA-256 verifies the corresponding Word media drawing. No credentials
or delivery ledger are consulted in proof mode.
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
    _read_original, allowed_official_resource, canonical_official_article,
    discover_official_newslist,
)
from scheduled_rasd import (
    MAX_BATCH, MAX_WORD_BYTES, digest_key, protected_credentials, send_one_word,
)

OFFICIAL_WORKFLOW = (
    "Hatem1984/RASD-Cloud-Monitor/.github/workflows/"
    "rasd-official-daily.yml@refs/heads/main"
)
APPROVED_WORDS = [
    "وزارة التخطيط", "وزير التخطيط", "وزيرة التخطيط",
    "التخطيط والتنمية الاقتصادية",
]


def require_official_scheduled_send(now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise RuntimeError("official_untrusted_clock")
    current = now.astimezone(CAIRO)
    if current.hour not in (22, 23):
        raise RuntimeError("official_daily_outside_delivery_window")
    expected = {
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": OFFICIAL_WORKFLOW,
    }
    if any(os.getenv(key) != val for key, val in expected.items()):
        raise RuntimeError("official_daily_not_authorized")
    kind = os.getenv("RASD_JOB_CRON")
    owner_oneoff = (
        kind in {"0 19 22 10 *", "30 19 22 10 *", "0 20 22 10 *"}
        and current.date() == date(2026, 10, 22)
        and current.hour in (22, 23)
    )
    persistent = (kind == "0 19,20 * * *"
                  and os.getenv("RASD_OFFICIAL_AUTOMATION_ENABLED") == "true")
    if not (owner_oneoff or persistent):
        raise RuntimeError("official_daily_not_explicitly_scheduled")
    if not os.getenv("GITHUB_RUN_ID", "").isdigit():
        raise RuntimeError("official_run_identity_missing")


def build_official_daily(output: Path, *, target_date: date,
                         config_path: Path = Path("sources.json"),
                         browser_factory=None) -> tuple[Path, list[dict]]:
    """Scan publisher's *actual* NewsList page 1, capture every same-day item.

    This is an honest official-source-limited bulletin, not an exhaustive
    newsroom crawler or all-history search. Any included evidence failure
    aborts, and no partial/invented JPEG or unverified file is retained.
    """
    if type(target_date) is not date:
        raise ValueError("official_invalid_cairo_date")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if cfg.get("keywords") != APPROVED_WORDS:
        raise ValueError("official_keywords_modified")
    output.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    factory = browser_factory or sync_playwright
    accepted = []
    with factory() as playwright:
        browser = playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = browser.new_context(
                viewport={"width": 1200, "height": 900}, locale="ar-EG",
                ignore_https_errors=False, accept_downloads=False,
                service_workers="block")
            context.route("**/*", lambda route: (
                route.continue_() if allowed_official_resource(route.request.url)
                else route.abort()))
            current = discover_official_newslist(context.request, max_articles=35)
            repeated = discover_official_newslist(context.request, max_articles=35)
            if not current or current != repeated:
                raise RuntimeError("official_listing_changed_or_unavailable")
            page = context.new_page()
            for index, url in enumerate(current, 1):
                if canonical_official_article(url) != url:
                    raise RuntimeError("official_untrusted_discovered_url")
                original = _read_original(
                    page, url, APPROVED_WORDS, target_date,
                    output / f"official-original-{index:02d}.jpg")
                if original.get("status") != "verified":
                    if original.get("reason") == "publisher_date_mismatch_or_missing":
                        continue  # Outside today's verified original publication window.
                    raise RuntimeError("official_original_page_hold")
                if original["published_date_cairo"] != target_date.isoformat():
                    raise RuntimeError("official_date_evidence_mismatch")
                accepted.append(original)
                if len(accepted) > MAX_BATCH:
                    raise RuntimeError("official_daily_exceeds_15_source_items")
        finally:
            browser.close()
    if not accepted:
        raise RuntimeError("official_no_verified_new_original_today")
    report = {
        "title": "رصد | البيان الصحفي الرسمي للوزارة — " + target_date.isoformat(),
        "display_window_start": target_date.isoformat() + " 00:00 القاهرة",
        "display_window_end": target_date.isoformat() + " 23:59 القاهرة",
        "coverage": "OFFICIAL_SOURCE_ONLY",
        "verified_links": len(accepted),
        "articles": [{
            "headline": r["headline"],
            "source": "وزارة التخطيط والتنمية الاقتصادية — الموقع الرسمي",
            "url": r["url"],
            "published_at_cairo": r["published_date_cairo"] + " (date only)",
            "published_display_cairo": r["published_date_cairo"] + " — بدون ساعة نشر موثقة",
            "evidence_image_path": r["image_path"],
        } for r in accepted],
        "sources": [{
            "feed_id": "mped-official-original-NewsList-page-1",
            "status": "ok", "verified_links": len(accepted),
            "error_type": None,
        }],
        "limitations": (
            "تقرير منفصل عن الموقع الرسمي للوزارة، وليس رصدًا صحفيًا"
            " للمواقع الإخبارية. نطاق الاكتشاف: الصفحة الأولى فقط من"
            " قائمة أخبار الوزارة الأصلية. التوقيت المتاح هو تاريخ"
            " نشر اليوم وليس ساعة الخبر. كل صورة أصلية من صفحة"
            " الوزارة ومطابقة لبصمة الصورة المضمنة في Word."
        ),
    }
    word = output / f"RASD-Official-Original-{target_date.isoformat()}.docx"
    render_docx(report, word)
    proofs = [{"status": "verified", "sha256": r["sha256"]} for r in accepted]
    if not word_images_match_capture_digests(word, proofs):
        word.unlink(missing_ok=True)
        raise RuntimeError("official_daily_word_image_integrity_hold")
    if not 3000 <= word.stat().st_size <= MAX_WORD_BYTES:
        word.unlink(missing_ok=True)
        raise RuntimeError("official_daily_word_size_hold")
    return word, accepted


def run(*, mode: str, output: Path, clock: datetime | None = None,
        builder=build_official_daily) -> dict:
    if mode not in ("proof", "send"):
        raise ValueError("official_mode_invalid")
    now = clock or datetime.now(timezone.utc)
    if mode == "send":
        require_official_scheduled_send(now)
    day = now.astimezone(CAIRO).date()
    word, entries = builder(output, target_date=day)
    if mode == "proof":
        return {
            "status": "PROOF_READY_OFFICIAL_ONLY_NO_MAIL", "count": len(entries),
            "original_jpegs_in_word": len(entries),
            "path": str(word), "smtp_accepted": False,
            "source_scope": "official_ministry_not_newsroom",
        }
    sender, recipient, password, ledger = protected_credentials()
    key = digest_key("official-ministry-original-daily:" + day.isoformat())
    reserved = ledger.reserve(key, recipient)
    if reserved != "reserved":
        raise RuntimeError("official_daily_private_duplicate_hold")
    subject = "رصد | نشرة البيانات الرسمية المصورة — " + day.isoformat()
    receipt = send_one_word(
        word, sender=sender, recipient=recipient, password=password,
        subject=subject, key=key)
    ledger.mark_smtp_accepted(key, receipt)
    return {
        "status": "OFFICIAL_SOURCE_SMTP_ACCEPTED_NOT_INBOX_CONFIRMED",
        "count": len(entries), "smtp_accepted": True,
        "source_scope": "official_ministry_not_newsroom",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("proof", "send"), required=True)
    parser.add_argument("--outdir", type=Path)
    args = parser.parse_args()
    try:
        if args.outdir is None:
            with tempfile.TemporaryDirectory(prefix="rasd-official-live-") as folder:
                result = run(mode=args.mode, output=Path(folder))
                result.pop("path", None)
                print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        else:
            if args.mode != "proof":
                raise RuntimeError("official_send_cannot_persist_public_output")
            result = run(mode="proof", output=args.outdir)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    except Exception:
        # Do not print secrets, SMTP exceptions or content from web publishers.
        print("RASD_OFFICIAL_DAILY=HOLD_NO_UNVERIFIED_DELIVERY", flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
