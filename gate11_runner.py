"""Gate 11 manual bridge: live article -> verified screenshot -> private ledger -> SMTP.

No historical reference screenshots, no cron, no public email receipts.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

from capture_public import APPROVED_PUBLISHERS, allowed_url, capture_publisher
from delivery_bridge import PrivateGitHubLedger, deliver_reserved
from monitor import article_id, canonical_url, inspect

ENABLE_PHRASE = "YES_I_APPROVE_GMAIL_DELIVERY"
RUN_CONFIRMATION_PHRASE = "CONFIRM_ONE_MANUAL_RASD_GMAIL_RUN"

# Only reviewed, non-sensitive failure labels may reach PUBLIC Actions logs.
SAFE_CAPTURE_FAILURE_CODES = frozenset({
    "publisher_not_approved", "publisher_http_failure",
    "publisher_no_http_response", "publisher_access_refused",
    "publisher_article_unavailable", "publisher_rate_limited",
    "publisher_server_error",
    "redirect_outside_publisher", "page_content_unavailable",
    "not_a_planning_article", "screenshot_too_small",
    "visual_qa_too_small_dimensions", "visual_qa_blank_or_low_content",
    "visual_qa_invalid_image", "invalid_jpeg_signature",
    "TimeoutError", "Error", "url_mismatch", "title_mismatch",
})


def record_capture_rejection(results: dict, reason: str | None) -> None:
    """Aggregate fixed audit codes; never print URLs, exceptions or page text."""
    code = reason if isinstance(reason, str) and reason in SAFE_CAPTURE_FAILURE_CODES else "other"
    results["rejected_capture"] += 1
    counts = results["capture_rejection_reasons"]
    counts[code] = counts.get(code, 0) + 1



def candidate_from_feed(article: dict, config: dict, now: datetime) -> dict | None:
    """Reject old/undated/fixture/unverified articles before screenshot or email."""
    if article.get("selection") and article["selection"] != "live_feed_discovery":
        return None
    url, headline, rawdate = article.get("url"), article.get("headline"), article.get("published")
    if not all(isinstance(x, str) and x.strip() for x in (url, headline, rawdate)):
        return None
    if not isinstance(article.get("id"), str) or article["id"] != article_id(url):
        return None
    if any(mark in headline for mark in ("\r", "\n")):
        return None
    feed = next((x for x in config["feeds"] if x["name"] == article.get("source")), None)
    host = urlsplit(url).hostname
    if not feed or host not in feed["allowed_article_hosts"]:
        return None
    publisher = next((base for base in APPROVED_PUBLISHERS if
                      allowed_url(url, base)), None)
    if not publisher:
        return None
    try:
        published = parsedate_to_datetime(rawdate)
        if published.tzinfo is None:
            return None
        delta = now.astimezone(timezone.utc) - published.astimezone(timezone.utc)
        if delta < -timedelta(minutes=30) or delta > timedelta(hours=min(72, config["recent_hours"])):
            return None
    except (ValueError, TypeError, OverflowError):
        return None
    return {**article, "publisher": publisher, "selection": "live_feed_discovery"}


def eligible_candidates(inspection: dict, config: dict, now: datetime, limit: int = 2) -> list[dict]:
    """Prefer truly freshest publisher-verified items, independent of feed order."""
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("invalid_candidate_limit")
    valid = [
        candidate for article in inspection.get("matched_public_articles", [])
        if (candidate := candidate_from_feed(article, config, now)) is not None
    ]
    # candidate_from_feed already validated tz-aware dates and source hosts.
    valid.sort(
        key=lambda article: parsedate_to_datetime(article["published"]).astimezone(timezone.utc),
        reverse=True,
    )
    return valid[:limit]


def credentials(*, require_send_approval: bool = True) -> dict:
    # Preflight deliberately cannot send; it validates auth without needing
    # the separate consent flag required by the real dispatch path.
    if require_send_approval:
        if os.environ.get("RASD_GATE11_SEND_APPROVED") != ENABLE_PHRASE:
            raise RuntimeError("gmail_delivery_not_authorized")
        # Defense in depth: an accidentally retained static environment secret
        # must NEVER authorize unattended email from cron, push, or another ref.
        if (os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
                or os.environ.get("GITHUB_REF") != "refs/heads/main"):
            raise RuntimeError("gmail_delivery_requires_manual_main_dispatch")
        if (os.environ.get("GITHUB_REPOSITORY") != "Hatem1984/RASD-Cloud-Monitor"
                or os.environ.get("GITHUB_ACTOR", "").casefold() != "hatem1984"):
            raise RuntimeError("gmail_delivery_requires_approved_repo_owner")
        # Never let GitHub's rerun action reuse a previous manual approval.
        if (os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
                or not os.environ.get("GITHUB_RUN_ID", "").isdigit()):
            raise RuntimeError("gmail_delivery_requires_new_workflow_run")
        # A new human-entered confirmation for EACH manual workflow run.
        if os.environ.get("RASD_GATE11_RUN_CONFIRMATION") != RUN_CONFIRMATION_PHRASE:
            raise RuntimeError("gmail_delivery_requires_per_run_confirmation")
    names = ("RASD_GMAIL_USER", "RASD_APPROVED_RECIPIENT",
             "RASD_GMAIL_APP_PASSWORD", "RASD_PRIVATE_LEDGER_TOKEN")
    env = {name: os.environ.get(name, "") for name in names}
    if not all(env.values()):
        raise RuntimeError("missing_protected_delivery_configuration")
    if env["RASD_GMAIL_USER"] != env["RASD_APPROVED_RECIPIENT"]:
        raise RuntimeError("sender_recipient_identity_mismatch")
    return env


def run(mode: str, *, config_path: Path = Path("sources.json"),
        fetch=None, capture=capture_publisher, ledger_factory=PrivateGitHubLedger,
        deliver=deliver_reserved, clock=None) -> dict:
    if mode not in ("dry_run", "send"):
        raise ValueError("unknown_gate11_mode")
    auth = credentials() if mode == "send" else None
    config = json.loads(config_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc) if clock is None else clock
    if now.tzinfo is None:
        raise ValueError("naive_clock_forbidden")
    inspected = inspect(config, now=now, article_limit=200,
                        **({"fetch": fetch} if fetch else {}))
    candidates = eligible_candidates(inspected, config, now)
    ledger = ledger_factory(auth["RASD_PRIVATE_LEDGER_TOKEN"]) if auth and candidates else None
    source_records = inspected.get("sources", [])
    # Only already-public source IDs and exception CLASS names are logged.
    # No feed response body, URL, secrets or email identifiers enter logs.
    source_health = [
        {"feed_id": record["feed_id"], "status": record["status"],
         "error_type": record.get("error") if record["status"] != "ok" else None}
        for record in source_records
    ]
    results = {"mode": mode, "eligible": len(candidates), "captured": 0,
               "coverage_status": ("degraded" if any(x["status"] != "ok"
                                                      for x in source_records)
                                   else "healthy"),
               "source_health": source_health,
               "healthy_sources": sum(x["status"] == "ok" for x in source_records),
               "failed_sources": sum(x["status"] != "ok" for x in source_records),
               "verified_publisher_links": inspected["public_verified_publisher_links"],
               "planning_headline_matches": inspected["planning_headline_matches"],
               "smtp_accepted": 0, "already_accepted": 0,
               "manual_review_hold": 0, "rejected_capture": 0,
               "capture_rejection_reasons": {},
               "test_fixture_used": False, "scheduler_enabled": False}
    # Ephemeral hosted-runner directory, not the user's machine or a public artifact.
    with tempfile.TemporaryDirectory(prefix="rasd-g11-") as workdir:
        for article in candidates:
            dest = Path(workdir) / (article["id"] + ".jpg")
            capture_result = capture(article["url"], article["publisher"], dest)
            if not capture_result.get("ok"):
                record_capture_rejection(results, capture_result.get("reason"))
                continue
            if (canonical_url(capture_result.get("actual_url", "")) !=
                    canonical_url(article["url"])):
                record_capture_rejection(results, "url_mismatch")
                continue
            # The original publisher headline must agree with browser title.
            # A false negative is safer than attaching a different article.
            if article["headline"].strip()[:12] not in capture_result.get("title", ""):
                record_capture_rejection(results, "title_mismatch")
                continue
            results["captured"] += 1
            if mode == "send":
                outcome = deliver(
                    article, dest, sender=auth["RASD_GMAIL_USER"],
                    approved_recipient=auth["RASD_APPROVED_RECIPIENT"],
                    app_password=auth["RASD_GMAIL_APP_PASSWORD"], ledger=ledger)
                if outcome not in ("smtp_accepted", "already_accepted", "manual_review_hold"):
                    raise RuntimeError("unexpected_delivery_state")
                results[outcome] += 1
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry_run", "send"), default="dry_run")
    opts = parser.parse_args()
    try:
        result = run(opts.mode)
        # Public Actions log: only counts, no recipient, secret, URL or article data.
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if result["coverage_status"] == "degraded":
            # This is a GitHub Actions annotation, not a failure of safe
            # partial operation; operator can see which publisher failed.
            print("::warning::RASD news source coverage degraded; inspect source_health counts",
                  flush=True)
    except Exception:
        # An error could mean SMTP accepted the mail before a network failure.
        # Never retry automatically; keep the private reservation on HOLD.
        print("gate11_failed_closed; inspect private ledger and Gmail Sent before retry",
              flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
