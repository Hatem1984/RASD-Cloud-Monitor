"""Gate72: Cairo-calendar daily schedule planner with NO running scheduler.

No APScheduler, GitHub cron, SMTP, R2, private ledger or account access.
One planned report per fully completed Cairo day, idempotency matched to
Gate70 unified Word identity. No auto catch-up or fake owner approval.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from gate70_unified_word_delivery_no_send import unified_delivery_key

CAIRO = ZoneInfo("Africa/Cairo")
SAFE_HOUR = 8


def next_safe_cairo_tick(now: datetime) -> datetime:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("gate72_requires_aware_clock")
    current = now.astimezone(CAIRO)
    today_tick = datetime.combine(current.date(), time(hour=SAFE_HOUR), tzinfo=CAIRO)
    tick = today_tick if current < today_tick else today_tick + timedelta(days=1)
    # Cairo's 08:00 is never the non-existent/repeated DST transition hour.
    return tick


def dry_run_daily_plan(now: datetime) -> dict:
    """Informational plan; a valid future run NEVER authorizes delivery."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("gate72_requires_aware_clock")
    cairo = now.astimezone(CAIRO)
    local_tick = datetime.combine(
        cairo.date(), time(hour=SAFE_HOUR), tzinfo=CAIRO
    )
    target = cairo.date() - timedelta(days=1)
    if cairo < local_tick:
        status = "WAIT_CAIRO_LOCAL_08_00_NOT_DUE"
    elif cairo < local_tick + timedelta(hours=1):
        status = "DRYRUN_READY_WINDOW_ONLY"
    else:
        status = "MISSED_WINDOW_REQUIRE_OPERATOR_REVIEW_NO_AUTO_CATCHUP"
    next_tick=next_safe_cairo_tick(now)
    return {
        "status":status,
        "target_completed_cairo_day": target.isoformat(),
        "report_identity": unified_delivery_key(target),
        "current_cairo_day": cairo.date().isoformat(),
        "next_tick_cairo": next_tick.isoformat(),
        "next_tick_utc": next_tick.astimezone(timezone.utc).isoformat(),
        "requires_real_stage2_owner_review": True,
        "requires_source_evidence": True,
        "requires_explicit_transport_approval": True,
        "gmail_enabled": False,
        "r2_enabled": False,
        "production_scheduler_enabled": False,
        "job_dispatched": False,
        "email_sent": False,
        "production_approved": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(dry_run_daily_plan(
        datetime.now(timezone.utc)),sort_keys=True))
