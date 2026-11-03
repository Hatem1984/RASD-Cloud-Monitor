"""RASD owner's calendar-day 30-minute / 22:00 policy — QA ONLY.

No SMTP, ledger mutation, scheduler installation, GitHub write, or cloud publication.
Use with existing RSS discovery and publisher screenshot verifier. This file is
a reviewed, testable orchestration policy, NOT a substitute for evidence capture.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from monitor import _ministry_term_present
from event_identity import distinct_events
from scheduled_rasd import digest_key

CAIRO = ZoneInfo("Africa/Cairo")
DAILY_CLOSE = time(22, 0)
SLOT_MINUTES = 30

def published_in_cairo(story: dict) -> datetime:
    """Use the PUBLISHER's explicit timezone, not the RSS request timestamp.

    A legacy 'YYYY-mm-dd HH:MM EET/EEST' has no offset in the text, so ambiguous
    Cairo DST rollback clock hours are held instead of silently picking a fold.
    """
    value = story.get("published_at_cairo")
    if not isinstance(value, str):
        raise ValueError("publisher_publication_clock_missing")
    try:
        if re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d (EET|EEST)", value):
            bare = datetime.strptime(value[:16], "%Y-%m-%d %H:%M")
            first = bare.replace(tzinfo=CAIRO, fold=0)
            second = bare.replace(tzinfo=CAIRO, fold=1)
            if first.utcoffset() != second.utcoffset():
                raise ValueError("publisher_publication_dst_ambiguous")
            if first.tzname() != value[-4:].strip():
                # EET suffix is 3 characters; EEST is 4.
                if first.tzname() != value.split()[-1]:
                    raise ValueError("publisher_publication_zone_mismatch")
            result = first
        else:
            result = datetime.fromisoformat(value)
            if result.tzinfo is None or result.utcoffset() is None:
                raise ValueError("publisher_publication_clock_naive")
            result = result.astimezone(CAIRO)
        # Reject impossible local time after DST spring-forward gap.
        if result.astimezone(timezone.utc).astimezone(CAIRO).replace(tzinfo=None) != result.replace(tzinfo=None):
            raise ValueError("publisher_publication_dst_gap")
        return result
    except (TypeError, ValueError) as exc:
        raise ValueError("publisher_publication_clock_unverified") from exc

def in_owner_day(story: dict, report_date: date, as_of: datetime) -> bool:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("naive_scan_clock")
    local_now = as_of.astimezone(CAIRO)
    published = published_in_cairo(story)
    return (published.date() == report_date
            and time(0, 0) <= published.time().replace(tzinfo=None) <= DAILY_CLOSE
            and published <= local_now)

def matched_owner_topics(story: dict, settings: dict) -> list[str]:
    text = story.get("headline", "") + " " + story.get("publisher_excerpt", "")
    labels = []
    for topic in settings["topics"]:
        if not topic["enabled"]:
            continue
        matches = [_ministry_term_present(text, [alias]) for alias in topic["aliases"]]
        if (all(matches) if topic["match"] == "all" else any(matches)):
            labels.append(topic["label"])
    return labels

def validate_health(settings: dict, source_health: list[dict]) -> int:
    allowed = [item["id"] for item in settings["sources"] if item["enabled"]]
    actual = [item.get("feed_id") for item in source_health]
    if (len(set(allowed)) != len(allowed) or not allowed
            or actual != allowed or
            any(item.get("status") not in ("ok", "failed") for item in source_health)):
        raise ValueError("source_health_incomplete_or_out_of_order")
    return sum(x["status"] == "failed" for x in source_health)

def _original_ok(story: dict, evidence: dict) -> bool:
    """Proof is produced by trusted capture path; verify the file/digest again.

    Never accept an RSS image, a page thumbnail or an undocumented fallback.
    """
    proof = evidence.get(story["id"])
    if not isinstance(proof, dict) or proof.get("status") != "verified":
        return False
    if proof.get("story_id") != story["id"] or proof.get("original_url") != story["url"]:
        return False
    digest = proof.get("sha256")
    path = proof.get("screenshot_path")
    if (not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest)
            or not isinstance(path, str)):
        return False
    file = Path(path)
    return file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() == digest

def _eligible_story(story, settings, report_date, now):
    enabled_names = {s["name"] for s in settings["sources"] if s["enabled"]}
    if story.get("source") not in enabled_names or not in_owner_day(story, report_date, now):
        return False
    published_clock = published_in_cairo(story).strftime("%H:%M")
    return (settings.get("start", "00:00") <= published_clock <= settings.get("end", "22:00")
            and bool(matched_owner_topics(story, settings)))

def plan_halfhour(*, settings: dict, now: datetime, found: list[dict],
                  source_health: list[dict], ledger_entries: dict,
                  original_capture_receipts: dict) -> dict:
    """New verified stories => prepare one Word; otherwise NO EMAIL.

    No plan authorizes SMTP. A reserved story is an uncertain in-flight
    delivery and MUST NOT be retried automatically.
    """
    if settings.get("scan_minutes") != 30 or settings.get("send_at") != "22:00":
        raise ValueError("unapproved_schedule_config")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("naive_scan_clock")
    now_cairo = now.astimezone(CAIRO)
    failed = validate_health(settings, source_health)
    utc_now=now.astimezone(timezone.utc)
    slot=utc_now.replace(minute=(utc_now.minute//30)*30,second=0,microsecond=0).strftime("%Y-%m-%dT%H:%MZ")
    slot_key=digest_key("interval-slot:"+slot)
    base = {"qa_only": True, "smtp_allowed": False, "scan_minutes":30,
            "slot_reservation_key":slot_key,
            "report_day":now_cairo.date().isoformat(), "sources_failed":failed,
            "coverage":"PARTIAL" if failed else "SOURCE_LIMITED",
            "new_verified_count":0, "held_screenshots":0, "duplicate_or_reserved":0,
            "eligible_ids":[], "delivery_key":None}
    if now_cairo.time() >= DAILY_CLOSE:
        return dict(base, status="SKIP_FINAL_CUTOFF", reason="22_00_daily_rollup_has_priority")
    if slot_key in ledger_entries:
        return dict(base,status="ALREADY_INTERVAL_SLOT_RESERVED_NO_SEND",
                    reason="one_bulletin_max_per_30m_slot")
    news = []
    held = 0
    duplicates = 0
    seen = set()
    for story in found:
        if not _eligible_story(story, settings, now_cairo.date(), now):
            continue
        ident = story["id"]
        if ident in seen:
            continue
        seen.add(ident)
        if ident in ledger_entries:
            # reserved or accepted must both suppress resend.
            duplicates += 1
            continue
        if not _original_ok(story, original_capture_receipts):
            held += 1
            continue
        news.append(story)
    news.sort(key=lambda x: (published_in_cairo(x), x["id"]))
    historical_news = [v["news"] for v in ledger_entries.values()
                       if isinstance(v,dict) and v.get("kind")=="interval_item"
                       and v.get("status") in ("reserved","smtp_accepted")
                       and isinstance(v.get("news"),dict)]
    news, repeated_events = distinct_events(news, historical_news)
    duplicates += len(repeated_events)
    base.update(new_verified_count=len(news),held_screenshots=held,
                duplicate_or_reserved=duplicates,
                eligible_ids=[x["id"] for x in news])
    if not news:
        return dict(base, status=("HOLD_EVIDENCE_NO_SEND" if held else
                                  "NO_NEW_VERIFIED_NO_SEND"),
                    reason="retry_later_no_empty_mail")
    if len(news) > 15:
        return dict(base,status="HOLD_BATCH_LIMIT_NO_SEND",
                    reason="no_silent_truncation_or_unverified_partial")
    key = digest_key("interval:"+slot+":"+",".join(x["id"] for x in news))
    return dict(base,status="READY_WORD_QA_NOT_SENT",delivery_key=key,
                required_atomic_reservation="slot_key_plus_all_article_ids_in_one_private_CAS",
                reason="all_selected_original_screenshots_verified_require_word_integrity")

def plan_daily(*, settings: dict, report_date: date, now: datetime,
               ledger_entries: dict, source_health: list[dict],
               final_new_verified: list[dict] | None = None,
               final_original_receipts: dict | None = None) -> dict:
    """One 00:00–22:00 rollup of publisher-DATED verified news.

    Previously accepted half-hourly items can reappear in the *daily digest*
    on purpose. Re-sending the same half-hourly bulletin remains forbidden.
    Late fresh originals captured in the final scan can be included only after
    successful screenshot checks, and must not invent SMTP acceptance.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("naive_scan_clock")
    local=now.astimezone(CAIRO)
    if local.date()!=report_date or local.time()<DAILY_CLOSE:
        return {"status":"WAIT_UNTIL_22_CAIRO_NO_SEND","qa_only":True,"smtp_allowed":False}
    failed=validate_health(settings,source_health)
    # Use existing stable rollup key, independent of config version.
    key=digest_key("rollup:"+report_date.isoformat())
    if key in ledger_entries:
        return {"status":"ALREADY_RESERVED_OR_SENT_NO_SEND","delivery_key":key,
                "qa_only":True,"smtp_allowed":False}
    articles={}
    for entry in ledger_entries.values():
        if not isinstance(entry,dict) or entry.get("kind")!="interval_item":
            continue
        if entry.get("status")!="smtp_accepted":
            continue
        article=entry.get("news")
        if (isinstance(article,dict)
                and article.get("source") in {x["name"] for x in settings["sources"]}
                and in_owner_day(article, report_date, now)):
            # Already accepted under a prior approved keyword revision: never
            # erase the earlier bulletin from the same-day digest.
            articles[article["id"]]=article
    pending=0
    for article in final_new_verified or []:
        if not _eligible_story(article,settings,report_date,now):
            continue
        if article["id"] in articles:continue
        if article["id"] in ledger_entries: # reserved/uncertain => don't reinterpret as unsent
            continue
        if not _original_ok(article,final_original_receipts or {}):
            pending+=1
            continue
        articles[article["id"]]=article
    selected=sorted(articles.values(),key=lambda x:(published_in_cairo(x),x["id"]))
    if not selected:
        return {"status":"NO_ACCEPTED_NEWS_NO_EMPTY_MAIL","qa_only":True,
                "smtp_allowed":False,"sources_failed":failed,"held_images":pending,
                "delivery_key":key,"count":0}
    return {"status":"READY_DAILY_WORD_QA_NOT_SENT","qa_only":True,
            "smtp_allowed":False,"sources_failed":failed,"held_images":pending,
            "coverage":"PARTIAL" if failed or pending else "SOURCE_LIMITED",
            "delivery_key":key,"count":len(selected),
            "article_ids":[x["id"] for x in selected],
            "topic_counts":dict(Counter(label for x in selected
                             for label in matched_owner_topics(x,settings)))}
