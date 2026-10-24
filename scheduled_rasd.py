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
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit

from cloud_proof_report import proof_capture, word_images_match_capture_digests
from daily_report import CAIRO, cairo_display_time, render_docx
from delivery_bridge import PrivateGitHubLedger, now_iso, reserve_entry
from monitor import article_id, inspect
from gate11_runner import candidate_from_feed

EXPECTED_WORKFLOW = (
    "Hatem1984/RASD-Cloud-Monitor/.github/workflows/"
    "rasd-scheduled.yml@refs/heads/main"
)
HALF_HOUR_CRON = "7,18,37,48 * * * *"
BACKUP_HALF_HOUR_CRON = "13,43 * * * *"
BACKUP_WORKFLOW = (
    "Hatem1984/RASD-Cloud-Monitor/.github/workflows/"
    "rasd-schedule-backup.yml@refs/heads/main"
)
DAILY_CRON = "0 19,20 * * *"
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
    """Accept 22:00 Cairo in both seasons; avoid competing 22:00 interval send.

    The noon-ish second UTC candidate is rejected by its Cairo wall clock.
    The 22:00 half-hour tick is deliberately skipped: 22:30 is the next
    interval, whose accepted items belong to the following 22:00 rollup.
    """
    _, _, _ = cairo_window(now)
    local = now.astimezone(CAIRO)
    if cron in (HALF_HOUR_CRON, BACKUP_HALF_HOUR_CRON):
        return "skip" if local.hour == 22 and local.minute < 30 else "interval"
    if cron == DAILY_CRON:
        # GitHub schedule may start late. Continue accepting this day's
        # 22:00 report within the SAME Cairo hour; private rollup CAS still
        # prevents a second delivery. Never cross into the next hour/day.
        return "rollup" if local.hour == 22 else "skip"
    raise ValueError("unknown_schedule_event")


def require_github_scheduler() -> None:
    env = os.environ
    expected = {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
        "GITHUB_RUN_ATTEMPT": "1",
        "RASD_AUTOMATION_ENABLED": "true",
    }
    if any(env.get(k) != v for k, v in expected.items()):
        raise RuntimeError("scheduled_execution_not_authorized")
    if not env.get("GITHUB_RUN_ID", "").isdigit():
        raise RuntimeError("invalid_run_identity")
    event = env.get("GITHUB_EVENT_NAME")
    workflow_ref = env.get("GITHUB_WORKFLOW_REF")
    schedule_kind = env.get("RASD_JOB_CRON")
    if event == "schedule":
        if ((workflow_ref == EXPECTED_WORKFLOW and
             schedule_kind in (HALF_HOUR_CRON, DAILY_CRON)) or
            (workflow_ref == BACKUP_WORKFLOW and
             schedule_kind == BACKUP_HALF_HOUR_CRON)):
            return
        raise RuntimeError("unapproved_scheduled_workflow_or_cron")
    # Backup is strictly schedule-only: it must never turn a manual push or
    # a workflow_dispatch into a protected mail-sending entrypoint.
    if workflow_ref != EXPECTED_WORKFLOW:
        raise RuntimeError("backup_workflow_not_authorized_for_push")
    marker = env.get("RASD_OWNER_PUSH_CONFIRM")
    if (event != "push" or env.get("GITHUB_ACTOR") != "Hatem1984"
            or marker not in {
                "RASD-OWNER-DAILY-2026-10-23",
                "RASD-OWNER-NEWSROOM-2026-10-24",
            }):
        raise RuntimeError("owner_oneoff_delivery_not_authorized")
    local = datetime.now(timezone.utc).astimezone(CAIRO)
    day = local.date().isoformat()
    approved = ((marker == "RASD-OWNER-DAILY-2026-10-23"
                 and day == "2026-10-23" and local.hour == 22)
                or (marker == "RASD-OWNER-NEWSROOM-2026-10-24"
                    and day == "2026-10-24" and 14 <= local.hour < 21))
    if not approved:
        raise RuntimeError("owner_oneoff_delivery_outside_cairo_date_window")


def protected_credentials() -> tuple[str, str, str, PrivateGitHubLedger]:
    env = os.environ
    sender = env.get("RASD_GMAIL_SENDER", "").strip().lower()
    recipient = env.get("RASD_REPORT_TO", "").strip().lower()
    # Google displays app passwords grouped with spaces. Normalize only
    # whitespace in memory, matching the tested protected SMTP preflight.
    password = "".join(env.get("RASD_GMAIL_APP_PASSWORD", "").split())
    token = env.get("RASD_PRIVATE_LEDGER_TOKEN", "").strip()
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


def discover_interval_news(config: dict, now: datetime, *, inspector=inspect,
                           allow_degraded: bool = False,
                           source_records: list[dict] | None = None,
                           age_hours: int = 72) -> list[dict]:
    """Read ALL current saved-keyword matches before deciding the per-email cap.

    A bounded 72-hour recovery window catches publishable items after missed
    GitHub scheduler runs, provided the original RSS still exposes them.
    Previously reserved/sent items are filtered using the private ledger, and
    a publisher image HOLD is never treated as a delivery. An RSS feed that
    no longer exposes older entries cannot be reconstructed by this scan.
    The 15-story cap applies to each new message, never the discovered pool.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("naive_news_clock_forbidden")
    if type(age_hours) is not int or age_hours not in (24, 48, 72):
        raise ValueError("unapproved_newsroom_lookback")
    checked = now.astimezone(timezone.utc)
    observed = inspector(config, now=checked, article_limit=200,
                         require_complete_items=True)
    if observed.get("matched_article_pool_truncated") or len(observed["matched_public_articles"]) > 200:
        raise RuntimeError("news_inventory_silent_truncation_hold")
    if source_records is not None:
        source_records.extend({
            "feed_id": s["feed_id"], "status": s["status"]
        } for s in observed["sources"])
    if not allow_degraded and any(s["status"] != "ok" for s in observed["sources"]):
        raise RuntimeError("source_not_healthy")
    newest = {}
    for original in observed["matched_public_articles"]:
        candidate = candidate_from_feed(original, config, checked)
        if candidate is None:
            continue
        stamp = parsedate_to_datetime(candidate["published"])
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise RuntimeError("publisher_date_unverifiable")
        stamp = stamp.astimezone(timezone.utc)
        if not checked - timedelta(hours=age_hours) <= stamp <= checked:
            continue
        row = {"id": candidate["id"], "headline": candidate["headline"],
               "publisher_excerpt": candidate.get("publisher_excerpt", ""),
               "source": candidate["source"], "url": candidate["url"],
               "published_at_cairo": stamp.astimezone(CAIRO).strftime("%Y-%m-%d %H:%M %Z"),
               "published_display_cairo": cairo_display_time(stamp)}
        newest.setdefault(row["id"], (stamp, row))
    return [x[1] for x in sorted(newest.values(), key=lambda x: x[0], reverse=True)]


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




def prepare_source_limited_verified_word(items: list[dict], config: dict,
                                        output: Path, *, title: str,
                                        start: str, end: str,
                                        source_records: list[dict],
                                        pending_approved_news: int = 0,
                                        capture=proof_capture
                                        ) -> tuple[Path, list[dict], int, bool]:
    """Real original screenshots ONLY; blocked articles remain eligible for retry.

    A newsletter is explicitly marked source-limited when an approved feed or
    publisher page fails. This deliberately does not pretend complete coverage.
    Any integrity/identity exception stops the entire delivery before reserve.
    """
    if not items or len(items) > MAX_BATCH:
        raise ValueError("invalid_source_limited_batch")
    if len({a.get("id") for a in items}) != len(items):
        raise ValueError("duplicate_source_limited_article")
    expected_ids = [f["id"] for f in config["feeds"]]
    if (len(source_records) != len(expected_ids) or
            [s.get("feed_id") for s in source_records] != expected_ids or
            any(s.get("status") not in {"ok", "failed"} for s in source_records)):
        raise ValueError("source_health_metadata_missing_or_untrusted")
    # Fail before network/image I/O for ANY unsafe candidate.
    for article in items:
        validate_story(article, config)
    output.mkdir(parents=True, exist_ok=True)
    selected, verified = [], []
    rejected = 0
    for index, item in enumerate(items, 1):
        screenshot = output / f"publisher-{index:03d}.jpg"
        proof = capture(item, config["feeds"], screenshot)
        if proof.get("status") != "verified":
            # A known original-page refusal remains a traceable HOLD, not a
            # fabricated picture or an accepted ledger entry.
            if proof.get("status") != "hold":
                raise RuntimeError("invalid_original_capture_receipt")
            # Finite pre-approved categories only; never log URLs, bodies,
            # exception strings or credentials from the original website.
            safe_reason = proof.get("reason")
            from gate11_runner import SAFE_CAPTURE_FAILURE_CODES
            if safe_reason not in SAFE_CAPTURE_FAILURE_CODES:
                safe_reason = "other"
            print("::warning::RASD_ORIGINAL_IMAGE_HOLD"
                  f" publisher={item['source']!r} reason={safe_reason}",
                  flush=True)
            rejected += 1
            continue
        digest = proof.get("sha256")
        if (not isinstance(digest, str) or
                re.fullmatch(r"[0-9a-f]{64}", digest) is None or
                not screenshot.is_file() or
                hashlib.sha256(screenshot.read_bytes()).hexdigest() != digest):
            raise RuntimeError("original_capture_digest_mismatch")
        selected.append({**item, "evidence_image_path": str(screenshot)})
        verified.append({"id": item["id"], "status": "verified",
                         "sha256": digest})
    if not selected:
        raise RuntimeError("no_original_publisher_page_verified")
    if not 0 <= pending_approved_news <= 200:
        raise ValueError("invalid_deferred_news_count")
    degraded = bool(rejected or pending_approved_news or
                    any(s["status"] != "ok" for s in source_records))
    source_rows = [{
        "feed_id": row["feed_id"], "status": row["status"],
        "verified_links": sum(
            item["source"] == next(
                f["name"] for f in config["feeds"]
                if f["id"] == row["feed_id"])
            for item in selected),
        "error_type": None if row["status"] == "ok" else "original_feed_unavailable",
    } for row in source_records]
    limitations = (
        "كل صورة في التقرير ملتقطة من صفحة الناشر الأصلية ومطابقة لبصمة"
        " JPEG الموجودة فعليًا داخل ملف Word. المطابقة على مستوى"
        " الرابط المنشور، وليست تجميعًا تحريريًا للأحداث المستقلة."
    )
    if degraded:
        limitations += (
            f" تغطية جزئية معلنة: {rejected} روابط مطابقة تعذر إثبات صورها؛"
            f" {sum(s['status'] != 'ok' for s in source_records)}"
            " مصادر RSS لم تكن متاحة. الروابط المعلقة لم تُحسب"
            " كأخبار مُسلّمة ويمكن فحصها لاحقًا."
        )
    if pending_approved_news:
        limitations += (
            f" {pending_approved_news} أخبار جديدة معتمدة من RSS تنتظر فحص"
            " الصورة الأصلية في دورة الرصد التالية؛ ولم تُحسب مُسلّمة."
        )
    report = {
        "title": title + (" — نطاق جزئي" if degraded else ""),
        "display_window_start": start, "display_window_end": end,
        "coverage": "SOURCE_LIMITED" if degraded else "HEALTHY",
        "verified_links": len(selected), "articles": selected,
        "sources": source_rows, "limitations": limitations,
    }
    word = output / "RASD-News-With-Original-Screenshots.docx"
    render_docx(report, word)
    if not word_images_match_capture_digests(word, verified):
        word.unlink(missing_ok=True)
        raise RuntimeError("word_screenshot_identity_hold")
    if not 3000 <= word.stat().st_size <= MAX_WORD_BYTES:
        word.unlink(missing_ok=True)
        raise RuntimeError("gmail_attachment_size_hold")
    return word, selected, rejected, degraded


def prepare_first_verified_word(candidates: list[dict], config: dict, output: Path,
                                *, title: str, start: str, end: str,
                                capture=proof_capture) -> tuple[dict, Path, list[dict]]:
    """Select ONE genuine, independently verified article for manual mail QA.

    This is not the complete interval or daily report: those still require
    every selected original publisher screenshot, without fallback. A blocked
    publisher page is never replaced by RSS text, a generated image or an
    unapproved alternate website. No private reservation or SMTP occurs here.
    """
    if not candidates:
        raise RuntimeError("first_live_no_new_approved_story")
    if len(candidates) > MAX_BATCH:
        raise RuntimeError("first_live_excessive_unsent_news")
    for index, story in enumerate(candidates, start=1):
        try:
            doc, verified = prepare_word(
                [story], config, output / f"candidate-{index:02d}",
                title=title, start=start, end=end, capture=capture)
        except RuntimeError as error:
            if str(error) != "publisher_screenshot_hold":
                raise
            # Do not print publisher URL, page text or untrusted exceptions.
            print("RASD_FIRST_LIVE_CANDIDATE_CAPTURE=HOLD", flush=True)
            continue
        if len(verified) != 1 or verified[0].get("id") != story["id"] or (
                verified[0].get("status") != "verified"):
            raise RuntimeError("first_live_word_evidence_identity_hold")
        return story, doc, verified
    raise RuntimeError("first_live_no_verified_original_publisher_story")


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
                  subject: str, key: str, body_text: str | None = None) -> str:
    if sender == recipient or not re.fullmatch(r"[0-9a-f]{24}", key):
        raise ValueError("invalid_transport_identity")
    msg = EmailMessage()
    msg["From"], msg["To"] = sender, recipient
    msg["Subject"] = subject
    msg["Message-ID"] = f"<rasd-{key}@gmail.com>"
    msg["X-RASD-Delivery-ID"] = key
    msg.set_content(
        body_text if body_text is not None else
        "تقرير رصد صحفي آلي. المرفق Word يحوي لقطات شاشة"
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
    """Roll up accepted mail in (prior 22:00 Cairo, today's 22:00 Cairo].

    Calendar midnight is NOT the operational report cutoff. A news alert
    accepted at 22:30 cannot silently disappear from both daily reports.
    Filtering by durable SMTP accepted_at also survives Cairo DST switches.
    """
    cutoff = datetime.combine(date.fromisoformat(day), time(22, 0), tzinfo=CAIRO)
    previous = datetime.combine(cutoff.date() - timedelta(days=1),
                                time(22, 0), tzinfo=CAIRO)
    news = []
    for key, entry in state["entries"].items():
        if entry.get("kind") != "interval_item" or entry.get("status") != "smtp_accepted":
            continue
        accepted_raw = entry.get("accepted_at")
        if not isinstance(accepted_raw, str):
            raise RuntimeError("private_accepted_timestamp_missing")
        try:
            accepted = datetime.fromisoformat(accepted_raw)
        except ValueError:
            raise RuntimeError("private_accepted_timestamp_invalid") from None
        if accepted.tzinfo is None or accepted.utcoffset() is None:
            raise RuntimeError("private_accepted_timezone_missing")
        accepted = accepted.astimezone(CAIRO)
        if not previous <= accepted < cutoff:
            continue
        item = entry.get("news")
        if not isinstance(item, dict) or item.get("id") != key:
            raise RuntimeError("private_sent_news_corrupted")
        validate_story(item, config)
        news.append(item)
    if len(news) > MAX_ROLLUP:
        raise RuntimeError("rollup_exceeds_60_verified_items_manual_review")
    # All original items from each SENT Word must remain intact for Gmail
    # archive attachment verification. Fresh future intervals are filtered
    # for cross-publisher duplicates BEFORE sending and private reservation.
    return sorted(news, key=lambda x: (x["published_at_cairo"], x["id"]))

def run_scheduled(mode: str, clock: datetime | None = None) -> dict:
    require_github_scheduler()
    now = datetime.now(timezone.utc) if clock is None else clock
    schedule_kind = os.environ.get("RASD_JOB_CRON", "")
    owner_oneoff = mode in {"rollup_owner_once", "interval_owner_once"}
    if mode == "interval_owner_once" and (
            os.environ.get("RASD_OWNER_PUSH_CONFIRM") !=
            "RASD-OWNER-NEWSROOM-2026-10-24"):
        raise RuntimeError("wrong_owner_newsroom_marker")
    event = os.environ.get("GITHUB_EVENT_NAME")
    if owner_oneoff:
        if event != "push" or schedule_kind:
            raise RuntimeError("owner_oneoff_mode_event_mismatch")
        # One-time, exact owner-initiated backfill; never a regular push,
        # workflow_dispatch, another account, or a different Cairo day.
        local = now.astimezone(CAIRO)
        marker = os.environ.get("RASD_OWNER_PUSH_CONFIRM")
        approved = (
            (mode == "rollup_owner_once"
             and marker == "RASD-OWNER-DAILY-2026-10-23"
             and local.date().isoformat() == "2026-10-23"
             and local.hour == 22)
            or
            (mode == "interval_owner_once"
             and marker == "RASD-OWNER-NEWSROOM-2026-10-24"
             and local.date().isoformat() == "2026-10-24" and 14 <= local.hour < 21)
        )
        if not approved:
            raise RuntimeError("owner_oneoff_mode_outside_cairo_date_window")
        phase = "rollup" if mode == "rollup_owner_once" else "interval"
    else:
        # require_github_scheduler() already authenticates normal schedules.
        # Reject only real push contexts here; offline tests explicitly mock
        # the outer guard and must remain independent of ambient CI event.
        if event == "push":
            raise RuntimeError("manual_or_push_cannot_start_periodic_delivery")
        phase = scheduled_phase(schedule_kind, now)
    # GitHub may drop or delay the exact 22:00 Cairo event. The next
    # authentic half-hour schedule occurrence is allowed to reconcile ONE
    # missing daily bulletin from the most recent completed 22:00 window.
    # Never allow manual_dispatch, PR, alternate cron, or unbounded replay.
    recovery = mode == "rollup_recovery"
    if recovery and schedule_kind not in (HALF_HOUR_CRON, BACKUP_HALF_HOUR_CRON):
        raise RuntimeError("daily_recovery_not_half_hour_schedule")
    if phase == "skip" and not recovery:
        return {"status": "skip_non_target_cairo_slot", "smtp_accepted": False}
    # 22:07 and 22:18 Cairo are backup opportunities for the 22:00
    # bulletin; NEVER issue another interval email during its window.
    if recovery and phase == "skip":
        local = now.astimezone(CAIRO)
        if local.hour != 22 or local.minute < 7:
            return {"status": "skip_non_target_cairo_slot", "smtp_accepted": False}
    if mode != phase and not (recovery and phase in ("interval", "skip")) and not owner_oneoff:
        raise RuntimeError("scheduled_mode_cron_mismatch")
    sender, recipient, password, ledger = protected_credentials()
    config = json.loads(Path("sources_newsroom_active.json").read_text(encoding="utf-8"))
    window, day, start = cairo_window(now)
    if recovery:
        local = now.astimezone(CAIRO)
        target_date = (local.date() if local.hour >= 22
                       else local.date() - timedelta(days=1))
        day = target_date.isoformat()
    state, _ = ledger.read()
    with tempfile.TemporaryDirectory(prefix="rasd-scheduled-") as folder:
        output = Path(folder)
        if mode in ("interval", "interval_owner_once"):
            health = []
            available = discover_interval_news(
                config, now, allow_degraded=True, source_records=health,
                **({"age_hours":48} if mode == "interval_owner_once" else {}))
            if mode == "interval_owner_once":
                # Retrospective only: strictly Oct23 publisher timestamps.
                available = [a for a in available
                             if a["published_at_cairo"].startswith("2026-10-23 ")]
            unsent = [a for a in available if a["id"] not in state["entries"]]
            from event_identity import distinct_events
            history = [v["news"] for v in state["entries"].values()
                       if isinstance(v, dict)
                       and v.get("kind") == "interval_item"
                       and v.get("status") in ("reserved", "smtp_accepted")
                       and isinstance(v.get("news"), dict)]
            stories, repeated_events = distinct_events(unsent, history)
            if repeated_events:
                print("RASD_SAME_EVENT_HELD_COUNT=" + str(len(repeated_events)),
                      flush=True)
            if not stories:
                return {"status": "no_new_verified_news", "smtp_accepted": False}
            # Do not fail all delivery when an irregular GitHub cron lets
            # more than one Word's worth of newly published stories accumulate.
            # Oldest accepted publication goes first so backlog cannot age out
            # solely because newer feed items repeatedly take priority.
            stories = sorted(stories,
                             key=lambda a: (a["published_at_cairo"], a["id"]))
            waiting = max(0, len(stories) - MAX_BATCH)
            if waiting:
                print("::warning::RASD_VERIFIED_STORIES_BACKLOG_PENDING="
                      + str(waiting), flush=True)
                stories = stories[:MAX_BATCH]
            title = ("رصد | استدراك أخبار 23 أكتوبر بصور ناشريها الأصلية"
                     if mode == "interval_owner_once" else
                     "رصد | أخبار جديدة من الفحص الدوري | " + cairo_display_time(start))
            try:
                doc, delivered, held_count, limited = prepare_source_limited_verified_word(
                    stories, config, output, title=title,
                    start=cairo_display_time(start),
                    end=cairo_display_time(now), source_records=health,
                    **({"pending_approved_news":waiting} if waiting else {}))
            except RuntimeError as exc:
                # Every discovered, approved article was attempted, but NONE
                # had a verified original-publisher screenshot. This is a
                # source-access HOLD (not a system crash, fake success or
                # authorization to email RSS-only text). Do not reserve or
                # mutate private state: a later run can safely retry.
                # Any other issue (digest, DOCX, corruption, credentials)
                # remains a hard failure and must not be hidden.
                if str(exc) != "no_original_publisher_page_verified":
                    raise
                return {
                    "status": "hold_all_original_publisher_captures_unavailable",
                    "items": 0,
                    "eligible_articles": len(stories) + waiting,
                    "held_articles": len(stories),
                    "waiting_articles": waiting,
                    "smtp_accepted": False,
                    "coverage_status": "SOURCE_ACCESS_HOLD_NO_DELIVERY",
                }
            # Only successfully captured/embedded originals enter private CAS.
            # Blocked items remain unsent, so later scheduled scans can retry.
            reserve_stories(ledger, delivered, day)
            message_key = digest_key("interval:" + window + ":" + ",".join(x["id"] for x in delivered))
            subject = title + (" [تغطية جزئية/متأخرة]" if limited or waiting else "")
            receipt = send_one_word(doc, sender=sender, recipient=recipient,
                                    password=password, subject=subject, key=message_key)
            # SMTP accepts exactly one Word message containing N stories.
            # Persist all N receipts together in ONE private CAS commit, not
            # N separate writes that can leave a half-accepted daily rollup.
            ledger.mark_smtp_accepted_many(
                [article["id"] for article in delivered], receipt)
            return {"status": "smtp_accepted_unconfirmed_inbox",
                    "items": len(delivered), "source_limited": bool(limited or waiting),
                    "original_screenshots_held": held_count,
                    "waiting_approved_news": waiting}
        if mode in ("rollup", "rollup_recovery", "rollup_owner_once"):
            rollup_key = digest_key("rollup:" + day)
            if rollup_key in state["entries"]:
                return {"status": "rollup_already_reserved_or_sent", "smtp_accepted": False}
            stories = news_for_rollup(state, day, config)
            if not stories:
                # No accepted verified newsroom items is itself a genuine
                # daily operational fact. Deliver an explicitly labelled
                # ZERO-news status Word, NOT a fabricated news report.
                # No candidate or fake image is inserted.
                title = "رصد | تقرير حالة الرصد: لا أخبار مصوّرة مُسلّمة | " + day
                report = {
                    "title": title,
                    "display_window_start": "الساعة 22:00 من اليوم السابق بتوقيت القاهرة",
                    "display_window_end": day + " 22:00 القاهرة",
                    "coverage": "NO_ACCEPTED_VERIFIED_NEWS",
                    "verified_links": 0,
                    "articles": [],
                    "sources": [],
                    "limitations": (
                        "هذا تقرير حالة تشغيل وليس تقرير تغطية صحفية كاملة. "
                        "لم تُقبل أي رسائل نصف ساعية تحتوي صور صفحات ناشرين "
                        "موثقة ضمن نافذة الـ24 ساعة المنتهية عند 22:00 القاهرة. "
                        "العدد صفر يخص الرسائل المقبولة في سجل التسليم الخاص "
                        "ولا يثبت عدم نشر أخبار في السوق؛ قد تكون أخبار "
                        "منشورة لكن التقاط صفحة الناشر أو قراءة RSS معلقًا."
                    ),
                }
                doc = output / "RASD-Daily-No-Verified-News-Status.docx"
                render_docx(report, doc)
                from docx import Document
                if (not doc.is_file() or
                        not 3000 <= doc.stat().st_size <= MAX_WORD_BYTES or
                        Document(doc).inline_shapes):
                    doc.unlink(missing_ok=True)
                    raise RuntimeError("daily_status_word_integrity_hold")
                no_news = True
            else:
                title = "رصد | التقرير المجمع للأخبار المرسلة | " + day
                try:
                    if os.environ.get("RASD_DAILY_SENT_ARCHIVE_ENABLED") == "true":
                        # Production daily report is ONE consolidated copy
                        # of already DELIVERED originals, never a new browser
                        # visit that the publisher may now block.
                        from daily_sent_consolidator import consolidate_sent_words
                        doc, _ = consolidate_sent_words(
                            stories, state, output, sender=sender,
                            recipient=recipient, app_password=password,
                            title=title,
                            start="الساعة 22:00 من اليوم السابق بتوقيت القاهرة",
                            end=day + " 22:00 القاهرة", config=config)
                    else:
                        # Offline legacy/test mode: no IMAP and no new sends.
                        doc, _ = prepare_word(
                            stories, config, output, title=title,
                            start="الساعة 22:00 من اليوم السابق بتوقيت القاهرة",
                            end=day + " 22:00 القاهرة")
                    photo_hold = False
                except RuntimeError as exc:
                    # A publisher can revoke public browser access AFTER an
                    # alert was genuinely delivered. Do not fabricate/omit
                    # accepted stories or turn any integrity error into success.
                    if str(exc) != "publisher_screenshot_hold":
                        raise
                    title = ("رصد | تقرير حالة: أخبار مُرسلة وصورها غير متاحة"
                             " لإعادة الالتقاط | " + day)
                    report = {
                        "title": title,
                        "display_window_start":
                            "الساعة 22:00 من اليوم السابق بتوقيت القاهرة",
                        "display_window_end": day + " 22:00 القاهرة",
                        "coverage": "PREVIOUSLY_ACCEPTED_NEWS_IMAGE_HOLD",
                        "verified_links": len(stories),
                        "articles": stories,  # Source URLs and titles, no images.
                        "sources": [],
                        "limitations": (
                            "هذه نشرة حالة للمراسلات المُثبتة في السجل الخاص"
                            " وليست التقرير اليومي المصوّر النهائي. الأخبار"
                            " التالية كانت قد أُرسلت بصورها الأصلية في رسائل"
                            " نصف ساعية سابقة، لكن صور الصفحات تعذّر إعادة"
                            " التقاطها الآن من الناشر؛ لا نختلق صورًا بديلة."
                            " راجع التنبيهات الأصلية المحفوظة في البريد."
                        ),
                    }
                    doc = output / "RASD-Daily-Sent-News-Image-HOLD.docx"
                    render_docx(report, doc)
                    from docx import Document
                    if (not doc.is_file() or
                            not 3000 <= doc.stat().st_size <= MAX_WORD_BYTES or
                            len(Document(doc).inline_shapes) != 0):
                        doc.unlink(missing_ok=True)
                        raise RuntimeError("daily_image_hold_word_integrity_hold")
                    photo_hold = True
                no_news = False
            reservation = ledger.reserve(rollup_key, recipient)
            if reservation != "reserved":
                return {"status": "rollup_not_reserved", "smtp_accepted": False}
            status_notice = no_news or (not no_news and photo_hold)
            description = (
                "تقرير حالة تشغيل RASD مرفق في ملف Word. هذا المستند"
                " ليس تقريرًا صحفيًا مصورًا. لا توجد أخبار مصوّرة مُسلّمة"
                " ضمن النافذة، وقد تكون صفحات الناشرين معلّقة.\n"
                if no_news else (
                    "تنبيه RASD: روابط وعناوين الأخبار التي سبق إرسالها"
                    " موثقة في Word، لكن إعادة التقاط صور الناشرين"
                    " تعذّرت. هذا تقرير حالة دون صور، وليس تقريرًا"
                    " صحفيًا مصورًا نهائيًا.\n" if photo_hold else None))
            mail_args = {
                "sender": sender, "recipient": recipient, "password": password,
                "subject": title, "key": rollup_key,
            }
            if status_notice:
                mail_args["body_text"] = description
            receipt = send_one_word(doc, **mail_args)
            ledger.mark_smtp_accepted(rollup_key, receipt)
            return {
                "status": (
                    "daily_no_verified_news_status_smtp_accepted_unconfirmed_inbox"
                    if no_news else (
                        "daily_image_hold_status_smtp_accepted_unconfirmed_inbox"
                        if photo_hold else "daily_smtp_accepted_unconfirmed_inbox")),
                "items": len(stories),
                "is_explicit_zero_accepted_news_notice": no_news,
                "is_explicit_image_capture_hold_notice": (
                    not no_news and photo_hold),
            }
    raise RuntimeError("unsupported_scheduled_mode")



# Only fixed, reviewed failure codes may leave the public GitHub runner.
# Never print an exception's arbitrary text, URL, secret or private ledger.
PUBLIC_SCHEDULED_HOLD_CODES = frozenset({
    "private_ledger_commit_not_visible",
    "private_ledger_commit_receipt_invalid",
    "private_ledger_request_failed",
    "private_ledger_read_invalid",
    "private_ledger_payload_invalid",
    "batch_reservation_not_eligible",
    "news_already_reserved_or_sent",
    "smtp_receipt_persistence_uncertain_manual_reconcile",
    "smtp_uncertain_reconcile_sent_manually",
    "word_screenshot_identity_hold",
    "gmail_attachment_size_hold",
    "source_not_healthy",
    "news_inventory_silent_truncation_hold",
    "rollup_exceeds_60_verified_items_manual_review",
    "daily_status_word_integrity_hold",
    "original_capture_digest_mismatch",
})


def safe_scheduled_hold_reason(error: Exception) -> str:
    """Expose only allowlisted operational diagnosis; no raw exception text."""
    if type(error) in (RuntimeError, ValueError):
        if str(error) in PUBLIC_SCHEDULED_HOLD_CODES:
            return str(error)
    return "other_held_failure"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["interval", "interval_owner_once", "rollup", "rollup_recovery", "rollup_owner_once", "dry_run"],
        required=True)
    args = parser.parse_args()
    if args.mode == "dry_run":
        # NO credentials, private state, browser or SMTP.
        slot, day, _ = cairo_window(datetime.now(timezone.utc))
        print(json.dumps({"mode": "dry_run_no_network", "slot": slot, "cairo_day": day,
                          "smtp_sent": False, "schedule_live": False}))
        return
    try:
        result = run_scheduled(args.mode)
        if result.get("status") == "hold_all_original_publisher_captures_unavailable":
            print("::warning::RASD_SOURCE_ACCESS_HOLD: all approved original"
                  " publisher pages unavailable to hosted browser;"
                  " 0 emails, 0 private reservations; retry at next scheduled slot.",
                  flush=True)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        print("RASD_SCHEDULED_HOLD_REASON="
              + safe_scheduled_hold_reason(error), flush=True)
        print("RASD_SCHEDULED_HOLD: inspect protected state; no blind resend")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()