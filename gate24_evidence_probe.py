"""Gate 24: bounded REAL original-publisher screenshot acceptance on the cloud.

Public feed and Chromium only. Screenshot JPEGs remain in a temporary directory
and are deleted before return. Output contains only allowlisted diagnostics,
not article URLs, headlines, page bodies, or private state.
This does NOT create a daily report, send email, or activate schedules.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from capture_public import capture_publisher
from cloud_proof_report import proof_capture
from daily_report import gather
from gate11_runner import SAFE_CAPTURE_FAILURE_CODES
from monitor import read_feed


def acceptance_probe(config_path: Path, *, fetch=read_feed,
                     capture=capture_publisher,
                     clock: datetime | None = None,
                     max_attempts: int = 1) -> dict:
    """Attempt no more than two eligible original articles; never fake evidence."""
    if type(max_attempts) is not int or not 1 <= max_attempts <= 2:
        raise ValueError("invalid_evidence_probe_attempt_limit")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    now = clock or datetime.now(timezone.utc)
    report = gather(config, fetch=fetch, now=now)
    matches = report["articles"][:max_attempts]
    attempts = []
    with tempfile.TemporaryDirectory(prefix="rasd-g24-") as folder:
        for row in matches:
            destination = Path(folder) / (row["id"] + ".jpg")
            # proof_capture verifies publisher allowlist, article URL hash, page
            # title/URL identity, JPEG dimensions/content and SHA256 integrity.
            try:
                result = proof_capture(row, config["feeds"], destination,
                                       capture=capture)
            except Exception:
                result = {"status": "hold", "reason": "other"}
            reason = result.get("reason", "other")
            if result["status"] != "verified" and reason not in SAFE_CAPTURE_FAILURE_CODES:
                reason = "other"
            attempts.append({
                "feed_id": next((f["id"] for f in config["feeds"]
                                if f["name"] == row["source"]), "unknown"),
                "status": "verified" if result["status"] == "verified" else "hold",
                "reason": None if result["status"] == "verified" else reason,
                "sha256_verified": result["status"] == "verified",
            })
    verified = sum(row["status"] == "verified" for row in attempts)
    refused = sum(row["reason"] == "publisher_access_refused" for row in attempts)
    return {
        "mode": "gate24_real_publisher_sample_probe",
        "scope": "single_sample_only_not_daily_report",
        "status": "SAMPLE_VERIFIED_ONLY" if verified == len(attempts) and attempts
                  and report["coverage"] == "HEALTHY" else
                  ("NO_ELIGIBLE_ARTICLES" if not attempts else "HOLD"),
        "coverage": report["coverage"],
        "sources": [
            {"feed_id": row["feed_id"], "status": row["status"],
             "error_type": row["error_type"]} for row in report["sources"]
        ],
        "verified_publisher_links": report["verified_links"],
        "eligible_within_24h": report["window_article_count"],
        "attempts": len(attempts), "verified_screenshots": verified,
        "publisher_access_refusals": refused,
        "failures_by_reason": dict(sorted(Counter(
            row["reason"] for row in attempts if row["reason"]).items())),
        "by_feed": attempts,
        "daily_word_created": False,
        "all_article_images_verified": False,
        "email_sent": False,
        "scheduler_enabled": False,
        "private_state_used": False,
        "browser_bypass_used": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("gate24-output"))
    parser.add_argument("--max-attempts", type=int, default=1)
    args = parser.parse_args()
    # No public filename, URL, or newspaper page text is accepted as a CLI arg.
    try:
        data = acceptance_probe(Path("sources.json"),
                                max_attempts=args.max_attempts)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        dest = args.output_dir / "gate24-redacted-audit.json"
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(json.dumps(data, ensure_ascii=False), flush=True)
        if data["status"] != "SAMPLE_VERIFIED_ONLY":
            print("::warning::Gate24 original-publisher sample evidence remains HOLD or no eligible story",
                  flush=True)
    except Exception:
        # Never print raw exception text (which may contain sensitive page URLs).
        print("gate24_evidence_probe_failed_closed", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
