"""MA'AL evidence-event journal contract. ISOLATED QA: not production connected.

The journal is independent from SMTP acceptance and the private delivery CAS.
An operator must implement a SEPARATE private durable CAS backend and immutable
original-JPEG storage before any live rollout. No imports from delivery_bridge.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import re

CAIRO = ZoneInfo("Africa/Cairo")
HEX = re.compile(r"^[0-9a-f]{24}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
STATES = frozenset(("VERIFIED_ORIGINAL", "EVIDENCE_HOLD"))
SCHEMA = "RASD_VERIFIED_EVENT_JOURNAL_V1"


class JournalHold(ValueError):
    """Invalid or unproven data: never silently downgrade verification."""


class CASConflict(RuntimeError):
    """Stale journal snapshot; retry read/recompute, never replay email."""


def empty_journal():
    return {"schema": SCHEMA, "revision": 0, "events": {}, "daily": {}}


def _instant(value):
    if not isinstance(value, str):
        raise JournalHold("invalid_instant")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise JournalHold("invalid_instant") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise JournalHold("timezone_required")
    return parsed.astimezone(timezone.utc)


def _validate(event):
    if not isinstance(event, dict):
        raise JournalHold("invalid_event")
    if not HEX.fullmatch(str(event.get("event_id", ""))):
        raise JournalHold("invalid_event_id")
    kind = event.get("status")
    if kind not in STATES:
        raise JournalHold("invalid_event_status")
    observed = _instant(event.get("first_verified_at") if kind == "VERIFIED_ORIGINAL"
                        else event.get("first_held_at"))
    if observed > datetime.now(timezone.utc) + timedelta(days=2):
        raise JournalHold("future_evidence_timestamp")
    url = urlsplit(event.get("original_url", ""))
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
        raise JournalHold("invalid_publisher_url")
    if (not isinstance(event.get("headline"), str)
            or not 1 <= len(event["headline"].strip()) <= 500
            or not isinstance(event.get("publisher"), str)
            or not 1 <= len(event["publisher"].strip()) <= 180):
        raise JournalHold("invalid_article_identity")
    if kind == "VERIFIED_ORIGINAL":
        proof = event.get("proof")
        if (not isinstance(proof, dict)
                or proof.get("type") != "ORIGINAL_PUBLISHER_JPEG"
                or not SHA.fullmatch(str(proof.get("sha256", "")))
                or not isinstance(proof.get("immutable_ref"), str)
                or not proof["immutable_ref"].startswith("private-evidence://")
                or not proof.get("publisher_page_match") is True
                or not proof.get("word_embed_digest_verified") is True):
            raise JournalHold("unverified_original_evidence")
    else:
        if event.get("proof") is not None or not event.get("hold_reason"):
            raise JournalHold("held_event_cannot_claim_original_proof")
    return observed


def validate_journal(state):
    if not isinstance(state, dict) or set(state) != {"schema", "revision", "events", "daily"}:
        raise JournalHold("invalid_journal_schema")
    if state["schema"] != SCHEMA or type(state["revision"]) is not int or state["revision"] < 0:
        raise JournalHold("invalid_journal_revision")
    if not isinstance(state["events"], dict) or not isinstance(state["daily"], dict):
        raise JournalHold("invalid_journal_members")
    if len(state["events"]) > 25000:
        raise JournalHold("journal_capacity_hold")
    for key, event in state["events"].items():
        if key != event.get("event_id"):
            raise JournalHold("journal_key_mismatch")
        _validate(event)
    for day, receipt in state["daily"].items():
        try:
            date.fromisoformat(day)
        except ValueError:
            raise JournalHold("invalid_daily_key") from None
        if (not isinstance(receipt, dict) or receipt.get("status") not in
                ("reserved", "smtp_accepted", "inbox_verified", "uncertain_hold")
                or not SHA.fullmatch(str(receipt.get("event_set_sha256", "")))):
            raise JournalHold("invalid_daily_reservation")
    return state


def append_event(state, event, *, expected_revision):
    """No SMTP interaction. Atomic caller CAS required for persistence."""
    validate_journal(state)
    _validate(event)
    if expected_revision != state["revision"]:
        raise CASConflict("stale_verified_event_revision")
    existing = state["events"].get(event["event_id"])
    if existing is not None:
        if existing == event:
            return deepcopy(state), "unchanged"
        # Allow explicit HOLD -> VERIFIED on independent, later evidence only.
        if (existing["status"] != "EVIDENCE_HOLD"
                or event["status"] != "VERIFIED_ORIGINAL"
                or _instant(event["first_verified_at"]) < _instant(existing["first_held_at"])):
            raise JournalHold("conflicting_or_regressed_event")
    result = deepcopy(state)
    result["events"][event["event_id"]] = deepcopy(event)
    result["revision"] += 1
    return result, "verified" if event["status"] == "VERIFIED_ORIGINAL" else "held"


def day_sections(state, day):
    """Cairo [00:00,22:00) plus previous-day [22:00,00:00) explicitly.

    By evidence FIRST VERIFIED timestamp, NOT email accepted timestamp.
    Verified after 22:00 belongs to the NEXT local calendar-day report,
    including the carryover in its separate late-night section.
    """
    validate_journal(state)
    requested = date.fromisoformat(day)
    midnight = datetime.combine(requested, time(), CAIRO)
    previous_22 = datetime.combine(requested - timedelta(days=1), time(22), CAIRO)
    current_22 = datetime.combine(requested, time(22), CAIRO)
    main, late, held = [], [], []
    for event in state["events"].values():
        timestamp = _validate(event).astimezone(CAIRO)
        if not previous_22 <= timestamp < current_22:
            continue
        if event["status"] == "EVIDENCE_HOLD":
            held.append(event)
        elif timestamp < midnight:
            late.append(event)
        else:
            main.append(event)
    key = lambda e: (e["first_verified_at"] if e["status"] == "VERIFIED_ORIGINAL"
                      else e["first_held_at"], e["event_id"])
    return {"day": day, "eligible_00_22": sorted(main, key=key),
            "late_previous_22_00": sorted(late, key=key),
            "held_not_deliverable": sorted(held, key=key),
            "complete_source_coverage_proven": False}


def reserve_daily(state, day, *, expected_revision, one_report_sha256):
    """Single day reservation. Uncertain SMTP never replays automatically."""
    validate_journal(state)
    if expected_revision != state["revision"]:
        raise CASConflict("stale_daily_revision")
    if not SHA.fullmatch(str(one_report_sha256)):
        raise JournalHold("invalid_daily_document_digest")
    view = day_sections(state, day)
    if day in state["daily"]:
        return deepcopy(state), "already_reserved_or_sent"
    ids = sorted(e["event_id"] for e in
                 view["eligible_00_22"] + view["late_previous_22_00"])
    digest = sha256(("\n".join(ids)).encode("utf-8")).hexdigest()
    final = deepcopy(state)
    final["daily"][day] = {
        "status": "reserved",
        "event_set_sha256": digest,
        "report_sha256": one_report_sha256,
        "eligible": len(ids),
        "held": len(view["held_not_deliverable"]),
    }
    final["revision"] += 1
    return final, "reserved"


def mark_daily_outcome(state, day, status, *, expected_revision):
    """Only delivery-reconciliation layer may call; no outbound SMTP here."""
    validate_journal(state)
    if expected_revision != state["revision"]:
        raise CASConflict("stale_daily_revision")
    if status not in ("smtp_accepted", "uncertain_hold", "inbox_verified"):
        raise JournalHold("invalid_daily_outcome")
    current = state["daily"].get(day)
    if current is None or current["status"] not in ("reserved", "smtp_accepted"):
        raise JournalHold("daily_outcome_not_eligible")
    if status == "inbox_verified" and current["status"] != "smtp_accepted":
        raise JournalHold("inbox_unverified")
    final = deepcopy(state)
    final["daily"][day]["status"] = status
    final["revision"] += 1
    return final
