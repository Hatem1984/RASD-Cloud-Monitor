"""Hourly RASD delivery gate: one protected batch per UTC/Cairo clock hour.

The source reader can still run on redundant half-hour GitHub/Cloudflare
ticks. Only the *first half of each hour* normally permits dispatch, except
22:00 Cairo: the protected 22:00 daily rollup goes first, and the 22:30+
hourly opportunity recovers 21:00-22:00 originals without overlap. Reserved slot + article keys share ONE private CAS transaction.
No network, SMTP or automatic retry is performed by this module.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

from delivery_bridge import now_iso, reserve_entry


def hourly_delivery_eligible(now: datetime, cairo) -> bool:
    """One half-hour per Cairo hour; 22:00 daily is a separate reservation.

    22:37 sends the 21:00-22:00 news after the 22:00 daily cutoff, so it
    belongs to the NEXT day's accepted-news rollup, never retroactive edit.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("hourly_clock_timezone_required")
    local = now.astimezone(cairo)
    return (local.hour == 22 and local.minute >= 30) or (
        local.hour != 22 and local.minute < 30)


def hourly_period(now: datetime) -> tuple[datetime, datetime, str]:
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        raise ValueError("hourly_clock_timezone_required")
    end = now.astimezone(timezone.utc).replace(
        minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=1)
    return start, end, end.strftime("%Y-%m-%dT%H:00Z")


def hourly_slot_key(slot: str) -> str:
    if (not isinstance(slot, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:00Z", slot)):
        raise ValueError("hourly_slot_invalid")
    # Preserve old per-article and daily keys. Slot namespace is new.
    return hashlib.sha256(
        ("rasd-scheduled-v1:hourly-slot:" + slot).encode()
    ).hexdigest()[:24]


def reserve_hourly_originals(ledger, stories: list[dict],
                             day: str, slot: str) -> str:
    """CAS all article IDs + hourly reservation together before SMTP.

    Existing reservation is a manual-reconciliation HOLD, never an excuse
    to resend within an hour. Release of this slot is not automatic even
    if the sender's SMTP outcome later becomes uncertain.
    """
    if (not isinstance(stories, list) or not 1 <= len(stories) <= 15
            or len({item.get("id") for item in stories}) != len(stories)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)):
        raise ValueError("hourly_original_reservation_invalid")
    slot_key = hourly_slot_key(slot)
    state, sha = ledger.read()
    if slot_key in state["entries"]:
        raise RuntimeError("hourly_delivery_slot_reserved_manual_review")
    if any(row["id"] in state["entries"] for row in stories):
        raise RuntimeError("hourly_story_already_reserved")
    instant = now_iso()
    pending, action = reserve_entry(state, slot_key, instant)
    if action != "reserved":
        raise RuntimeError("hourly_delivery_slot_reserved_manual_review")
    pending["entries"][slot_key].update({
        "kind": "hourly_slot", "day_cairo": day,
        "item_ids": [row["id"] for row in stories],
    })
    for item in stories:
        pending, action = reserve_entry(pending, item["id"], instant)
        if action != "reserved":
            raise RuntimeError("hourly_story_reservation_failed")
        pending["entries"][item["id"]].update({
            "kind": "interval_item", "day_cairo": day,
            "news": {field: item[field] for field in (
                "id", "headline", "publisher_excerpt", "source", "url",
                "published_at_cairo", "published_display_cairo")},
        })
    ledger.write(pending, sha)
    return slot_key
