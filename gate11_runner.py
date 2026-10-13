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
    found = []
    for article in inspection.get("matched_public_articles", []):
        valid = candidate_from_feed(article, config, now)
        if valid:
            found.append(valid)
        if len(found) >= limit:
            break
    return found


def credentials() -> dict:
    if os.environ.get("RASD_GATE11_SEND_APPROVED") != ENABLE_PHRASE:
        raise RuntimeError("gmail_delivery_not_authorized")
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
    inspected = inspect(config, now=now, **({"fetch": fetch} if fetch else {}))
    candidates = eligible_candidates(inspected, config, now)
    ledger = ledger_factory(auth["RASD_PRIVATE_LEDGER_TOKEN"]) if auth and candidates else None
    results = {"mode": mode, "eligible": len(candidates), "captured": 0,
               "smtp_accepted": 0, "already_accepted": 0,
               "manual_review_hold": 0, "rejected_capture": 0,
               "test_fixture_used": False, "scheduler_enabled": False}
    # Ephemeral hosted-runner directory, not the user's machine or a public artifact.
    with tempfile.TemporaryDirectory(prefix="rasd-g11-") as workdir:
        for article in candidates:
            dest = Path(workdir) / (article["id"] + ".jpg")
            capture_result = capture(article["url"], article["publisher"], dest)
            if not capture_result.get("ok") or (
                canonical_url(capture_result.get("actual_url", "")) !=
                    canonical_url(article["url"])
            ):
                results["rejected_capture"] += 1
                continue
            # The original publisher headline must agree with browser title.
            # A false negative is safer than attaching a different article.
            if article["headline"].strip()[:12] not in capture_result.get("title", ""):
                results["rejected_capture"] += 1
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
    except Exception:
        # An error could mean SMTP accepted the mail before a network failure.
        # Never retry automatically; keep the private reservation on HOLD.
        print("gate11_failed_closed; inspect private ledger and Gmail Sent before retry",
              flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
