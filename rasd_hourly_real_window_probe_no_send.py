"""Live one-completed-Cairo-hour source-yield audit; strictly NO SEND.

Exactly one immutable UTC interval represents the completed Cairo clock hour,
including DST transitions. Read the approved original feeds, classify each
candidate by original publication timestamp and publisher/event, and print
counts only. Never mistake RSS candidates for proven visual Word articles.
No private ledger, Gmail, SMTP, images, recipients or state changes.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from daily_report import CAIRO
from scheduled_rasd import discover_interval_news
from rasd_strict_hourly_ten_source_gate import (
    audit_fresh_distinct_sources, last_completed_hour,
)


def main() -> None:
    if (os.environ.get("RASD_AUTOMATION_ENABLED") != "false"
            or os.environ.get("RASD_HOURLY_REPORTS_ENABLED") != "false"
            or os.environ.get("RASD_DAILY_VOLUME_DELIVERY_ENABLED") != "false"):
        raise RuntimeError("read_only_hourly_probe_requires_all_delivery_disabled")
    config = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    now = datetime.now(timezone.utc)
    start, end = last_completed_hour(now)
    source_records = []
    candidates = discover_interval_news(
        config, now, allow_degraded=True,
        source_records=source_records, published_before=end,
    )
    audit = audit_fresh_distinct_sources(
        candidates, config["feeds"], now, required=10, max_items=15,
    )
    if len(audit["candidate_decisions"]) != len(candidates):
        raise RuntimeError("hourly_candidate_decisions_incomplete_hold")
    status_counts = {
        "healthy": sum(s.get("status") == "ok" for s in source_records),
        "failed": sum(s.get("status") == "failed" for s in source_records),
    }
    # Publisher-owned safe source IDs and fixed failure codes only.
    result = {
        "sample_kind": "actual_completed_cairo_clock_hour",
        "observed_cairo": now.astimezone(CAIRO).isoformat(timespec="seconds"),
        "from_cairo": start.astimezone(CAIRO).isoformat(timespec="seconds"),
        "until_cairo_exclusive": end.astimezone(CAIRO).isoformat(timespec="seconds"),
        "from_utc": start.isoformat(),
        "until_utc_exclusive": end.isoformat(),
        "sources_checked": len(source_records),
        "sources_healthy": status_counts["healthy"],
        "sources_failed": status_counts["failed"],
        "source_failures": [
            {"id": s["feed_id"], "code": s.get("failure_code", "other")}
            for s in source_records if s.get("status") == "failed"
        ],
        "original_rss_candidates_checked": len(candidates),
        "fresh_distinct_rss_candidates_needing_original_photo": (
            audit["fresh_distinct_candidates"]
        ),
        "rejection_counts": audit["rejection_counts"],
        "decision_count": len(audit["candidate_decisions"]),
        "verified_original_photos_for_this_hour": False,
        "hourly_smtp_sent": False,
        "private_ledger_read": False,
        "private_ledger_mutated": False,
        "production_acceptance_proven": False,
    }
    print("RASD_ACTUAL_COMPLETED_HOUR_NO_SEND=" +
          json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
