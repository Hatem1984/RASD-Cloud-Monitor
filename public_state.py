"""Durable public-news observation fingerprints, independent of Gmail or delivery.

ONLY SHA-256-based IDs derived from already-public publisher URLs are persisted.
An 'observed' article MUST NOT be labeled as emailed or delivered.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_SCHEMA = 1
ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")
MAX_IDS = 20000
KEEP_DAYS = 90


def empty_state() -> dict:
    return {"schema_version": STATE_SCHEMA, "run_count": 0,
            "last_successful_scan_utc": None, "seen_ids": {}}


def validate_state(state: dict) -> dict:
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA:
        raise ValueError("unsupported_public_state_version")
    run_count = state.get("run_count")
    seen = state.get("seen_ids")
    if type(run_count) is not int or run_count < 0 or not isinstance(seen, dict) or len(seen) > MAX_IDS:
        raise ValueError("invalid_public_state_shape")
    if any(not isinstance(k, str) or not ID_PATTERN.fullmatch(k)
           or not isinstance(v, str) for k, v in seen.items()):
        raise ValueError("invalid_public_state_fingerprint")
    return state


def load_state(path: Path) -> dict:
    if not path.exists():
        return empty_state()
    return validate_state(json.loads(path.read_text(encoding="utf-8")))


def apply_observations(state: dict, probe: dict, clock: datetime) -> tuple[dict, dict]:
    """Commit only observed URL hashes after a successful public feed scan.

    This tracks rediscovery across cloud runs, NOT delivery or notification.
    """
    validate_state(state)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("utc_aware_clock_required")
    if not any(s.get("status") == "ok" for s in probe.get("sources", [])):
        raise ValueError("no_verified_public_source")
    clock = clock.astimezone(timezone.utc)
    keep_after = clock - timedelta(days=KEEP_DAYS)
    fresh = {}
    for key, raw in state["seen_ids"].items():
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed.astimezone(timezone.utc) >= keep_after:
                fresh[key] = raw
        except (ValueError, TypeError, OverflowError):
            raise ValueError("invalid_state_timestamp")
    new_count = already_seen = 0
    # These are already-public article URLs; persist only stable ID and timestamp.
    for article in probe.get("matched_public_articles", []):
        key = article.get("id", "")
        if not isinstance(key, str) or not ID_PATTERN.fullmatch(key):
            raise ValueError("invalid_article_fingerprint")
        if key in fresh:
            already_seen += 1
        else:
            if len(fresh) >= MAX_IDS:
                raise ValueError("fingerprint_store_capacity_exceeded")
            fresh[key] = clock.isoformat(timespec="seconds")
            new_count += 1
    result = {"schema_version": STATE_SCHEMA,
              "run_count": state["run_count"] + 1,
              "last_successful_scan_utc": clock.isoformat(timespec="seconds"),
              "seen_ids": fresh}
    stats = {"run_number_in_public_state": result["run_count"],
             "matched_in_current_feed": len(probe.get("matched_public_articles", [])),
             "newly_observed_public_articles": new_count,
             "already_observed_public_articles": already_seen,
             "total_stored_public_url_fingerprints": len(fresh),
             "delivery_attempted": False,
             "state_semantics": "public_url_observed_not_emailed"}
    return result, stats


def save_state(path: Path, state: dict):
    validate_state(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
