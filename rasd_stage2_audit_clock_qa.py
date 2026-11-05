"""Resolve which Cairo day a delayed 22:10 daily QA audit is allowed to review.

GitHub Actions schedules are best-effort and may run after midnight.
The audit must never accidentally examine a new day's empty 44 slots.
This module has no network, email, or secret access.
"""
from __future__ import annotations
import argparse
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")
AUDIT_CLOCK = time(22, 10)
MAX_DELAY = timedelta(hours=8)


def target_day_for_daily_audit(now: datetime):
    """Most recent planned 22:10 Cairo, accepted only within eight real hours.

    If GitHub starts much later, fail closed instead of silently assigning
    the run to some later day. Never create or backfill an observation slot.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("daily_audit_clock_must_be_aware")
    here = now.astimezone(CAIRO)
    day = here.date()
    planned = datetime.combine(day, AUDIT_CLOCK, tzinfo=CAIRO)
    if here.astimezone(timezone.utc) < planned.astimezone(timezone.utc):
        day = day - timedelta(days=1)
        planned = datetime.combine(day, AUDIT_CLOCK, tzinfo=CAIRO)
    delta = now.astimezone(timezone.utc) - planned.astimezone(timezone.utc)
    if not timedelta(0) <= delta <= MAX_DELAY:
        raise ValueError("daily_audit_clock_too_late_hold")
    return day


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-day", action="store_true", required=True)
    args = parser.parse_args()
    if args.print_day:
        # No event timestamps inferred: actual time determines the last
        # eligible scheduled audit. Late >=8h jobs fail explicitly.
        print(target_day_for_daily_audit(datetime.now(timezone.utc)).isoformat())


if __name__ == "__main__":
    main()
