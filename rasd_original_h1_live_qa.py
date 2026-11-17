"""One real original-page image QA on existing approved feeds. NEVER SEND.

Strict native RSS discovery -> approved article identity -> publisher HTML
screenshot, headline and JPEG verification. Images and URLs remain ephemeral
and are not uploaded to public Actions. This is a sample, not a daily report.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cloud_proof_report import proof_capture
from gate11_runner import SAFE_CAPTURE_FAILURE_CODES, candidate_from_feed
from monitor import inspect


def run_one(*, inspector=inspect, proof=proof_capture) -> dict:
    config = json.loads(Path("sources_newsroom_active.json").read_text(
        encoding="utf-8"))
    now = datetime.now(timezone.utc)
    observed = inspector(config, now=now, article_limit=200,
                         require_complete_items=True)
    feed_ids = {feed["name"]: feed["id"] for feed in config["feeds"]}
    discovered = []
    for row in observed["matched_public_articles"]:
        if row.get("source") not in feed_ids:
            continue
        article = candidate_from_feed(row, config, now)
        if article:
            discovered.append((feed_ids[row["source"]], article))
    counts = {
        "checked_sources": len(observed["sources"]),
        "failed_sources": sum(s["status"] != "ok"
                              for s in observed["sources"]),
        "eligible_candidates": len(discovered),
    }
    receipt = {"status": "NO_CURRENT_ELIGIBLE_SAMPLE",
               "publisher_id": None, "image_verified": False,
               "reason": None}
    with tempfile.TemporaryDirectory(prefix="rasd-h1-live-qa-") as tmp:
        if discovered:
            publisher_id, article = discovered[0]
            result = proof(article, config["feeds"], Path(tmp) / "original.jpg")
            good = result.get("status") == "verified"
            reason = result.get("reason")
            receipt = {
                "status": "ORIGINAL_PAGE_VERIFIED" if good else "IMAGE_HOLD",
                "publisher_id": publisher_id,
                "image_verified": good,
                "reason": (None if good else reason if
                           reason in SAFE_CAPTURE_FAILURE_CODES else "other")
            }
    return {
        "mode": "RASD_ORIGINAL_H1_ONE_LIVE_QA_NO_SEND",
        **counts, **receipt,
        "sample_only": True,
        "original_page_or_photo_substituted": False,
        "new_sources_activated": False,
        "private_state_used": False,
        "email_sent": False,
        "artifact_uploaded": False,
    }


def main():
    print(json.dumps(run_one(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
