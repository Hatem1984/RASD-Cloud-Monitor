"""Safe offline FOUR-WORD preview; optional read-only approved web probe.

NEVER sends email or mutates delivery ledger. Social sources are HOLD until
approved official access and independently verified post/screenshot bindings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from daily_report import CAIRO
from rasd_four_reports_review import build_four_reports, hourly_window
from rasd_social_review_bridge import approved_social_probe


def approved_web_probe(*, now: datetime, evidence_root: Path,
                       discover=None, capture=None) -> tuple[list[dict], list[dict]]:
    """Live read-only original RSS + verified publisher screenshot path.

    No private CAS, SMTP, mail, or social session. The chosen feed set is
    exactly sources_newsroom_active.json; expansion candidates stay out.
    """
    from scheduled_rasd import discover_interval_news
    from cloud_proof_report import proof_capture
    discover = discover or discover_interval_news
    capture = capture or proof_capture
    config_path = Path(__file__).with_name("sources_newsroom_active.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    health: list[dict] = []
    news = discover(config, now, allow_degraded=True,
                    source_records=health, age_hours=24)
    if (len(health) != len(config["feeds"])
            or [s["feed_id"] for s in health] !=
               [s["id"] for s in config["feeds"]]):
        raise RuntimeError("approved_web_source_health_incomplete_hold")
    start, end = hourly_window(now)
    statuses = []
    for row, profile in zip(health, config["feeds"]):
        statuses.append({
            "channel": "web", "name": profile["name"],
            "status": "ok" if row["status"] == "ok" else "unavailable",
        })
    feeds_by_name = {f["name"]: f for f in config["feeds"]}
    collected = []
    for n, candidate in enumerate(news):
        if candidate.get("source") not in feeds_by_name:
            raise RuntimeError("publisher_not_approved_hold")
        try:
            # Candidate producer derives this from the publisher's original
            # timezone-aware RSS stamp. The formatted Cairo stamp has minute
            # precision; DST transition ambiguity requires source recheck.
            raw_local = candidate["published_at_cairo"][:16]
            published = datetime.strptime(raw_local, "%Y-%m-%d %H:%M")
            published = published.replace(tzinfo=CAIRO).astimezone(timezone.utc)
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("publisher_timestamp_recheck_required_hold") from None
        if not start <= published < end:
            continue
        dest = evidence_root / ("approved-web-" + str(n) + ".jpg")
        try:
            proof = capture(candidate, config["feeds"], dest)
        except (OSError, RuntimeError, ValueError):
            proof = {"status": "hold"}
        if proof.get("status") != "verified":
            # A visible HOLD overrides a technically healthy RSS feed.
            for state in statuses:
                if state["name"] == candidate["source"]:
                    state["status"] = "hold"
            continue
        digest = proof.get("sha256", "")
        if (not isinstance(digest, str) or not dest.is_file()
                or hashlib.sha256(dest.read_bytes()).hexdigest() != digest):
            raise RuntimeError("publisher_original_capture_digest_hold")
        collected.append({
            "channel": "web", "platform": None,
            "title": candidate["headline"], "source": candidate["source"],
            "url": candidate["url"], "published_at": published.isoformat(),
            "image_path": str(dest), "image_sha256": digest,
            "capture_receipt": {"status": "verified",
                                "url": candidate["url"], "sha256": digest,
                                "method": "approved_web_publisher_capture"},
        })
    return collected, statuses


def run_no_send(*, now: datetime, final_day: date, output: Path,
                probe_web: bool = False, discover=None, capture=None,
                probe_social: bool = False, capture_social: bool = False,
                social_collector=None, social_screenshot=None,
                social_config: dict | None = None,
                social_environment: dict | None = None) -> dict:
    """Produces four separate drafts. Real social/daily always remain HOLD."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_required_hold")
    config = json.loads(
        Path(__file__).with_name("sources_newsroom_active.json")
        .read_text(encoding="utf-8"))
    allowed_hosts = {h for f in config["feeds"]
                     for h in f["allowed_article_hosts"]}
    output.mkdir(parents=True, exist_ok=True)
    evidence = output / "evidence"
    evidence.mkdir(exist_ok=True)
    if probe_web:
        items, web_health = approved_web_probe(
            now=now, evidence_root=evidence, discover=discover, capture=capture)
    else:
        items = []
        web_health = [
            {"channel": "web", "name": f["name"],
             "status": "not_configured"} for f in config["feeds"]]
    if probe_social:
        social_items, social_health, social_summary = approved_social_probe(
            now=now, evidence_root=evidence,
            collect=social_collector, screenshot=social_screenshot,
            capture_originals=capture_social, config=social_config,
            environment=social_environment)
        items.extend(social_items)
    else:
        social_health = [
            {"channel": "social", "name": platform, "status": "not_configured"}
            for platform in ("Facebook", "X", "Instagram", "LinkedIn")]
        social_summary = {
            "api_candidates": 0, "independent_original_captures_verified": 0,
            "original_capture_hold": 0, "capture_authorized": False,
            "social_archive_receipts_verified": False, "smtp_sent": False,
        }
    health = web_health + social_health
    # Authenticated daily social acceptance is a separate, still-HOLD gate.
    # Never mint synthetic CAS receipts or treat API metadata as screenshots.
    summary = build_four_reports(
        items, health, [], cutoff=now, date_cairo=final_day,
        evidence_root=evidence, output=output,
        allowed_web_hosts=allowed_hosts)
    summary["live_web_probe_requested"] = bool(probe_web)
    summary["social_live_posts_verified"] = (
        social_summary["independent_original_captures_verified"])
    summary["social_collection"] = social_summary
    summary["daily_archive_read"] = False
    summary["email_sent"] = False
    (output / "RASD-Four-Reports-REVIEW-MANIFEST.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="RASD four Word review, NO SEND")
    parser.add_argument("--probe-approved-web", action="store_true",
                        help="Read approved RSS and capture original pages, NO SEND")
    parser.add_argument("--probe-approved-social", action="store_true",
                        help="Use ONLY configured/authorized official social APIs")
    parser.add_argument("--capture-approved-social", action="store_true",
                        help="Original post browser proof requires separate owner gates")
    parser.add_argument("--out", type=Path, default=Path("report-output/four-review"))
    args = parser.parse_args()
    if args.capture_approved_social and not args.probe_approved_social:
        parser.error("social capture requires approved social source probe")
    if args.probe_approved_social:
        protected = (Path(__file__).resolve().parent / "report-output").resolve()
        if not args.out.resolve().is_relative_to(protected):
            parser.error("social outputs must remain inside ignored report-output")
    now = datetime.now(timezone.utc)
    local = now.astimezone(CAIRO)
    # Last already completed 22:00 Cairo daily boundary, never a future day.
    final_day = local.date() if local.hour >= 22 else local.date().fromordinal(
        local.date().toordinal() - 1)
    result = run_no_send(
        now=now, final_day=final_day, output=args.out,
        probe_web=args.probe_approved_web,
        probe_social=args.probe_approved_social,
        capture_social=args.capture_approved_social)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
