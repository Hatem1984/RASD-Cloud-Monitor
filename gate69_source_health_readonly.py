"""Gate69: strictly read-only, source-health observation, NEVER a release gate.

Original two native RSS feeds plus the genuine official Ministry NewsList.
Publisher invalid XML remains HOLD: never repair, cache, substitute or send.
Seven independent completed Cairo days are required to claim *observed*
stability, not proof that an upstream publisher will never fail again.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from monitor import inspect
from official_ministry_source import discover_official_newslist

CAIRO = ZoneInfo("Africa/Cairo")
SOURCES = frozenset(("hapi", "almasryalyoum", "mped-official"))
LIMIT = 7


def validate_daily_sample(sample: dict, *, today_cairo: date) -> dict:
    """Return bounded redacted observation; reject untrusted/ambiguous input."""
    if type(sample) is not dict or type(today_cairo) is not date:
        raise ValueError("gate69_observation_invalid")
    try:
        day = date.fromisoformat(sample["day"])
    except (ValueError, TypeError, KeyError):
        raise ValueError("gate69_observation_date_invalid") from None
    if day >= today_cairo:
        raise ValueError("gate69_requires_completed_cairo_day")
    rows = sample.get("sources")
    if (type(rows) is not list or len(rows) != 3 or
            any(type(r) is not dict for r in rows) or
            {r.get("id") for r in rows} != SOURCES):
        raise ValueError("gate69_source_ids_invalid")
    for row in rows:
        if (set(row) != {"id", "ok", "original_links", "xml_error_code"}
                or type(row["ok"]) is not bool
                or type(row["original_links"]) is not int
                or not 0 <= row["original_links"] <= 10000
                or (row["id"] == "mped-official" and
                    row["ok"] and row["original_links"] == 0)):
            raise ValueError("gate69_source_row_invalid")
        code = row["xml_error_code"]
        if code is not None and (type(code) is not int or not 1 <= code <= 99):
            raise ValueError("gate69_xml_diagnostic_invalid")
        if row["ok"] and code is not None:
            raise ValueError("gate69_healthy_rss_xml_error_conflict")
        if not row["ok"] and row["original_links"] != 0:
            raise ValueError("gate69_failed_source_claimed_verified_links")
    return {
        "day": day.isoformat(),
        "source_health": [
            {key: r[key] for key in ("id", "ok", "original_links", "xml_error_code")}
            for r in sorted(rows, key=lambda x: x["id"])
        ],
        "all_sources_healthy": all(r["ok"] for r in rows),
    }


def evaluate_window(samples: list[dict], *, today_cairo: date) -> dict:
    if type(samples) is not list or not 1 <= len(samples) <= 31:
        raise ValueError("gate69_window_size_invalid")
    validated = [validate_daily_sample(s, today_cairo=today_cairo)
                 for s in samples]
    dates = [date.fromisoformat(s["day"]) for s in validated]
    if len(set(dates)) != len(dates):
        raise ValueError("gate69_duplicate_completed_day_forbidden")
    if dates != sorted(dates):
        raise ValueError("gate69_days_must_be_ascending")
    # Classify the LATEST seven DISTINCT completed calendar dates only.
    # Missing days and missing source checks prevent fake sustained uptime.
    recent = validated[-LIMIT:]
    days = [date.fromisoformat(x["day"]) for x in recent]
    consecutive = (len(days) == LIMIT and all(
        (days[i] - days[i - 1]).days == 1
        for i in range(1, len(days))
    ))
    all_ok = all(x["all_sources_healthy"] for x in recent)
    failure_days = [x["day"] for x in recent if not x["all_sources_healthy"]]
    status = (
        "HOLD_UPSTREAM_SOURCE" if failure_days else
        "OBSERVED_HEALTHY_7_DISTINCT_DAYS_NOT_UPSTREAM_GUARANTEE"
        if consecutive else "INSUFFICIENT_CONSECUTIVE_COMPLETED_DAYS"
    )
    return {
        "status": status,
        "observed_completed_days": len(recent),
        "consecutive_7_days": consecutive,
        "source_fail_days": failure_days,
        "all_7_samples_healthy": bool(consecutive and all_ok),
        "gmail_enabled": False, "r2_enabled": False,
        "scheduler_enabled": False, "production_approved": False,
        "source_changed": False, "keywords_changed": False,
    }


def public_live_probe() -> dict:
    """One low-volume REAL read; never print publisher text, IDs or URLs."""
    from playwright.sync_api import sync_playwright

    now = datetime.now(CAIRO)
    config = json.loads(Path("sources.json").read_text(encoding="utf-8"))
    if ([feed.get("id") for feed in config.get("feeds", [])] !=
            ["hapi", "almasryalyoum"] or
            config.get("keywords") != [
                "وزارة التخطيط", "وزير التخطيط",
                "وزيرة التخطيط", "التخطيط والتنمية الاقتصادية",
            ]):
        raise ValueError("gate69_config_not_approved")
    # validate every original RSS item, but log ONLY aggregate status.
    original = inspect(config, now=now, require_complete_items=True)
    rows = []
    for src in original["sources"]:
        rows.append({
            "id": src["feed_id"], "ok": src["status"] == "ok",
            "original_links": src["verified_links"] if src["status"] == "ok" else 0,
            "xml_error_code": src.get("xml_error_code") if src["status"] != "ok" else None,
        })
    # Real original trusted Ministry link discovery. URL bounded by the
    # already-reviewed existing adapter, not search, guessed IDs or RSS.
    ministry_links = 0
    try:
        with sync_playwright() as p:
            request = p.request.new_context(ignore_https_errors=False)
            try:
                links = discover_official_newslist(request, page_number=1)
                ministry_links = len(links)
            finally:
                request.dispose()
    except Exception:
        ministry_links = 0
    rows.append({
        "id": "mped-official", "ok": ministry_links > 0,
        "original_links": ministry_links, "xml_error_code": None,
    })
    result = {
        "day": now.date().isoformat(),
        "status": ("ALL_3_ORIGINAL_SOURCES_HEALTHY_QA_ONLY"
                   if all(x["ok"] for x in rows) else
                   "HOLD_ORIGINAL_SOURCE_HEALTH"),
        "sources": rows,
        "all_sources_healthy": all(x["ok"] for x in rows),
        "future_uptime_not_guaranteed": True,
        "report_created": False, "email_sent": False,
        "r2_used": False, "scheduler_enabled": False,
        "production_approved": False,
    }
    return result


if __name__ == "__main__":
    try:
        value = public_live_probe()
        print(json.dumps(value, sort_keys=True, ensure_ascii=True))
        if not value["all_sources_healthy"]:
            raise SystemExit(2)
    except SystemExit:
        raise
    except Exception:
        print(json.dumps({"status": "HOLD_ORIGINAL_SOURCE_HEALTH",
                          "report_created": False, "email_sent": False,
                          "r2_used": False, "scheduler_enabled": False,
                          "production_approved": False}, sort_keys=True))
        raise SystemExit(2) from None
