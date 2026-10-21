"""RASD scheduled cloud-only news digest; fail closed before email if incomplete.

This module is dormant until the repository owner provisions separate SMTP
credentials and explicitly enables the scheduled Actions environment.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import smtplib
import ssl
import tempfile
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit

from cloud_proof_report import proof_capture, word_images_match_capture_digests
from daily_report import CAIRO, gather, render_docx
from delivery_bridge import PrivateGitHubLedger, now_iso, reserve_entry
from monitor import article_id

EXPECTED_WORKFLOW = (
    "Hatem1984/RASD-Cloud-Monitor/.github/workflows/"
    "rasd-scheduled.yml@refs/heads/main"
)
HALF_HOUR_CRON = "0,30 * * * *"
DAILY_CRON = "50 20,21 * * *"
MAX_WORD_BYTES = 8_000_000
MAX_BATCH = 15  # Existing production limit, unchanged.
MAX_ROLLUP = 60


def cairo_window(now: datetime) -> tuple[str, str, datetime]:
    """Stable UTC slot ID; Cairo day correctly switches summer/winter DST."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_required")
    utc = now.astimezone(timezone.utc)
    minute = (utc.minute // 30) * 30
    start = utc.replace(minute=minute, second=0, microsecond=0)
    return start.strftime("%Y-%m-%dT%H:%MZ"), start.astimezone(CAIRO).date().isoformat(), start


def digest_key(value: str) -> str:
    return hashlib.sha256(("rasd-scheduled-v1:" + value).encode()).hexdigest()[:24]


def scheduled_phase(cron: str, now: datetime) -> str:
    """Ignore second daily UTC trigger and accept 23:50 Cairo in both seasons."""
    _, _, _ = cairo_window(now)
    if cron == HALF_HOUR_CRON:
        return "interval"
    if cron == DAILY_CRON:
        local = now.astimezone(CAIRO)
        return "rollup" if local.hour == 23 and local.minute >= 50 else "skip"
    raise ValueError("unknown_schedule_event")


def require_github_scheduler() -> None:
    env = os.environ
    expected = {
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": EXPECTED_WORKFLOW,
        "RASD_AUTOMATION_ENABLED": "true",
    }
    if any(env.get(k) != v for k, v in expected.items()):
        raise RuntimeError("scheduled_execution_not_authorized")
    if not env.get("GITHUB_RUN_ID", "").isdigit():
        raise RuntimeError("invalid_run_identity")


def protected_credentials() -> tuple[str, str, str, PrivateGitHubLedger]:
    env = os.environ
    sender = env.get("RASD_GMAIL_SENDER", "").strip().lower()
    recipient = env.get("RASD_REPORT_TO", "").strip().lower()
    password = env.get("RASD_GMAIL_APP_PASSWORD", "")
    token = env.get("RASD_PRIVATE_LEDGER_TOKEN", "")
    if not re.fullmatch(r"[^@\s]+@gmail\.com", sender):
        raise RuntimeError("sender_must_be_dedicated_gmail")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recipient):
        raise RuntimeError("recipient_invalid")
    if sender == recipient:
        raise RuntimeError("sender_and_recipient_must_differ")
    if len(password) < 12 or len(token) < 16:
        raise RuntimeError("missing_protected_credentials")
    ledger = PrivateGitHubLedger(token)
    state, _ = ledger.read()
    actual = hashlib.sha256(recipient.encode()).hexdigest()
    if not hmac.compare_digest(actual, state["approved_recipient_sha256"]):
        raise RuntimeError("private_ledger_recipient_not_approved")
    return sender, recipient, password, ledger


def validate_story(item: dict, config: dict) -> None:
    if item.get("id") != article_id(item.get("url", "")):
        raise ValueError("untrusted_story_identifier")
    matches = [f for f in config["feeds"] if f["name"] == item.get("source")]
    if len(matches) != 1 or urlsplit(item["url"]).hostname not in matches[0]["allowed_article_hosts"]:
        raise ValueError("unapproved_news_publisher")
    if not item.get("headline") or not item.get("published_at_cairo"):
        raise ValueError("incomplete_story")


def prepare_word(items: list[dict], config: dict, output: Path,
                 *, title: str, start: str, end: str,
                 capture=proof_capture) -> tuple[Path, list[dict]]:
    """Capture each ORIGINAL publisher page and verify its exact drawing in Word."""
    if not items or len(items) > MAX_ROLLUP:
        raise ValueError("no_stories_or_excessive_rollup")
    if len({x["id"] for x in items}) != len(items):
        raise ValueError("duplicate_story_ids")
    output.mkdir(parents=True, exist_ok=True)
    verified = []
    stories = []
    for index, item in enumerate(items):
        validate_story(item, config)
        screenshot = output / f"publisher-{index+1:03d}.jpg"
        result = capture(item, config["feeds"], screenshot)
        if result.get("status") != "verified":
            raise RuntimeError("publisher_screenshot_hold")
        copy = dict(item)
        copy["evidence_image_path"] = str(screenshot)
        stories.append(copy)
        verified.append({"id": item["id"], "status": "verified", "sha256": result["sha256"]})
    report = {
        "title": title, "display_window_start": start,
        "display_window_end": end, "coverage": "HEALTHY",
        "verified_links": len(stories), "articles": stories,
        "sources": [{"feed_id": f["id"], "status": "ok", "verified_links": 0,
                     "error_type": None} for f in config["feeds"]],
        "limitations": "تقرير صحفي من روابط ناشرين أصلية مع صور صفحات موثقة."
        " التكرار الدلالي للأحداث يحتاج مراجعة تحريرية؛ الرصد مقصور على"
        " مصادر RSS المعتمدة. لا اختلاق عند غياب الأخبار.",
    }
    dest = output / "RASD-News-With-Original-Screenshots.docx"
    render_docx(report, dest)
    if not word_images_match_capture_digests(dest, verified):
        dest.unlink(missing_ok=True)
        raise RuntimeError("word_screenshot_identity_hold")
    size = dest.stat().st_size
    if not 3000 <= size <= MAX_WORD_BYTES:
        dest.unlink(missing_ok=True)
        raise RuntimeError("gmail_attachment_size_hold")
    return dest, verified


def reserve_stories(ledger: PrivateGitHubLedger, stories: list[dict],
                    report_day: str) -> None:
    """One private compare-and-swap write BEFORE any SMTP attempt."""
    state, sha = ledger.read()
    for item in stories:
        if item["id"] in state["entries"]:
            raise RuntimeError("news_already_reserved_or_sent")
        state, action = reserve_entry(state, item["id"], now_iso())
        if action != "reserved":
            raise RuntimeError("news_reservation_failed")
        # Private metadata only; never write article bodies or JPEGs to public repo.
        state["entries"][item["id"]].update({
            "kind": "interval_item", "day_cairo": report_day,
            "news": {k: item[k] for k in (
                "id", "headline", "publisher_excerpt", "source", "url",
                "published_at_cairo", "published_display_cairo")},
        })
    ledger.write(state, sha)  # Independent readback enforces durable reservation.


def send_one_word(word: Path, *, sender: str, recipient: str, password: str,
                  subject: str, key: str) -> str:
    if sender == recipient or not re.fullmatch(r"[0-9a-f]{24}", key):
        raise ValueError("invalid_transport_identity")
    msg = EmailMessage()
    msg["From"], msg["To"] = sender, recipient
    msg["Subject"] = subject
    msg["Message-ID"] = f"<rasd-{key}@gmail.com>"
    msg["X-RASD-Delivery-ID"] = key
    msg.set_content("تقرير رصد صحفي آلي. المرفق Word يحوي لقطات شاشة"
                    " لصفحات الأخبار الأصلية، وعناوينها وتواريخها وروابطها.\n")
    msg.add_attachment(
        word.read_bytes(), maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=word.name,
    )
    # NEVER retry after an uncertain SMTP exception; private reservation stays HOLD.
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=25,
                              context=ssl.create_default_context()) as smtp:
            smtp.login(sender, password)
            refused = smtp.send_message(msg, from_addr=sender, to_addrs=[recipient])
            if refused:
                raise RuntimeError("recipient_refused")
    except Exception:
        raise RuntimeError("smtp_uncertain_reconcile_sent_manually") from None
    return str(msg["Message-ID"])


def news_for_rollup(state: dict, day: str, config: dict) -> list[dict]:
    """Daily digest reads ONLY articles confirmed SMTP-accepted that Cairo day."""
    news = []
    for key, entry in state["entries"].items():
        if (entry.get("kind") != "interval_item"
                or entry.get("day_cairo") != day
                or entry["status"] != "smtp_accepted"):
            continue
        item = entry.get("news")
        if not isinstance(item, dict) or item.get("id") != key:
            raise RuntimeError("private_sent_news_corrupted")
        validate_story(item, config)
        news.append(item)
    if len(news) > MAX_ROLLUP:
        raise RuntimeError("rollup_exceeds_60_verified_items_manual_review")
    return sorted(news, key=lambda x: (x["published_at_cairo"], x["id"]))


def run_scheduled(mode: str, clock: datetime | None = None) -> dict:
    require_github_scheduler()
    now = datetime.now(timezone.utc) if clock is None else clock
    phase = scheduled_phase(os.environ.get("RASD_JOB_CRON", ""), now)
    if phase == "skip":
        return {"status": "skip_wrong_cairo_daily_hour", "smtp_accepted": False}
    if mode != phase:
        raise RuntimeError("scheduled_mode_cron_mismatch")
    sender, recipient, password, ledger = protected_credentials()
    config = json.loads(Path("sources.json").read_text(encoding="utf-8"))
    window, day, start = cairo_window(now)
    state, _ = ledger.read()
    with tempfile.TemporaryDirectory(prefix="rasd-scheduled-") as folder:
        output = Path(folder)
        if mode == "interval":
            snapshot = gather(config, now=now, max_articles=MAX_BATCH)
            if snapshot["coverage"] != "HEALTHY" or snapshot["truncated"]:
                raise RuntimeError("feed_degraded_or_item_overflow")
            stories = [a for a in snapshot["articles"] if a["id"] not in state["entries"]]
            if not stories:
                return {"status": "no_new_verified_news", "smtp_accepted": False}
            title = "رصد | الأخبار الجديدة — نصف ساعة | " + window
            doc, _ = prepare_word(stories, config, output, title=title,
                                  start=start.astimezone(CAIRO).isoformat(),
                                  end=now.astimezone(CAIRO).isoformat())
            reserve_stories(ledger, stories, day)
            message_key = digest_key("interval:" + window + ":" + ",".join(x["id"] for x in stories))
            receipt = send_one_word(doc, sender=sender, recipient=recipient,
                                    password=password, subject=title, key=message_key)
            for article in stories:
                ledger.mark_smtp_accepted(article["id"], receipt)
            return {"status": "smtp_accepted_unconfirmed_inbox", "items": len(stories)}
        if mode == "rollup":
            rollup_key = digest_key("rollup:" + day)
            if rollup_key in state["entries"]:
                return {"status": "rollup_already_reserved_or_sent", "smtp_accepted": False}
            stories = news_for_rollup(state, day, config)
            if not stories:
                return {"status": "no_confirmed_items_for_daily_rollup", "smtp_accepted": False}
            title = "رصد | التقرير المجمع للأخبار المرسلة | " + day
            doc, _ = prepare_word(stories, config, output, title=title,
                                  start=day+" 00:00 القاهرة", end=day+" 23:50 القاهرة")
            reservation = ledger.reserve(rollup_key, recipient)
            if reservation != "reserved":
                return {"status": "rollup_not_reserved", "smtp_accepted": False}
            receipt = send_one_word(doc, sender=sender, recipient=recipient,
                                    password=password, subject=title, key=rollup_key)
            ledger.mark_smtp_accepted(rollup_key, receipt)
            return {"status": "daily_smtp_accepted_unconfirmed_inbox", "items": len(stories)}
    raise RuntimeError("unsupported_scheduled_mode")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["interval", "rollup", "dry_run"], required=True)
    args = parser.parse_args()
    if args.mode == "dry_run":
        # NO credentials, private state, browser or SMTP.
        slot, day, _ = cairo_window(datetime.now(timezone.utc))
        print(json.dumps({"mode": "dry_run_no_network", "slot": slot, "cairo_day": day,
                          "smtp_sent": False, "schedule_live": False}))
        return
    try:
        result = run_scheduled(args.mode)
        print(json.dumps(result, ensure_ascii=False))
    except Exception:
        print("RASD_SCHEDULED_HOLD: inspect protected state; no blind resend")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()