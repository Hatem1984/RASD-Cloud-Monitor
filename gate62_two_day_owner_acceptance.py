"""LOCAL two-distinct-completed-Cairo-day Stage2 Word evidence verifier.

No network, private key, mail, cloud writes, scheduler or automatic human
approval. This checks owner-local self-attestations against actual private
Word/page hashes; it DOES NOT sign identity or authorize production.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from gate61_owner_private_visual_review import (
    CAIRO, _json_file, inspect_private_review,
)

TYPE = "RASD_LOCAL_OWNER_SELF_ATTESTED_REVIEW_V1"
VERDICT = "TWO_DISTINCT_FULL_CAIRO_DAYS_LOCALLY_SELF_ATTESTED_NOT_PRODUCTION_APPROVAL"


def _one(folder: Path, day: date) -> dict:
    verified = inspect_private_review(folder, day)
    receipt_file = Path(folder) / "rasd-owner-human-review-attestation.json"
    receipt = _json_file(receipt_file)
    if (receipt.get("type") != TYPE or
            receipt.get("target_date_cairo") != day.isoformat() or
            receipt.get("human_visual_review") is not True or
            receipt.get("production_delivery_approved") is not False or
            receipt.get("word_sha256") != verified["word_sha256"] or
            receipt.get("page_sha256") != verified["page_sha256"] or
            type(receipt.get("review_page_count")) is not int or
            receipt["review_page_count"] != verified["review_page_count"]):
        raise ValueError("local_human_attestation_missing_or_mismatched")
    reviewed_at = receipt.get("reviewed_at_cairo")
    if type(reviewed_at) is not str or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+-]\d{2}:\d{2}",
        reviewed_at,
    ):
        raise ValueError("local_attestation_timestamp_invalid")
    try:
        stamp = datetime.fromisoformat(reviewed_at)
        local = stamp.astimezone(CAIRO)
        if stamp.utcoffset() is None or local.isoformat() != stamp.isoformat():
            raise ValueError("local_attestation_cairo_offset_invalid")
        day_end = datetime.combine(
            day + timedelta(days=1), datetime.min.time(), tzinfo=CAIRO,
        )
        if not day_end <= local <= datetime.now(CAIRO) + timedelta(minutes=2):
            raise ValueError("local_attestation_not_after_complete_day")
    except (OverflowError, ValueError) as exc:
        raise ValueError("local_attestation_timestamp_invalid") from exc
    return {
        "day": day.isoformat(),
        "article_count": verified["article_count"],
        "review_page_count": verified["review_page_count"],
        "word_sha256": verified["word_sha256"],
        "page_sha256": verified["page_sha256"],
        "local_self_attestation_present": True,
    }


def verify_two_completed_days(folder_a: Path, day_a: date,
                              folder_b: Path, day_b: date) -> dict:
    if type(day_a) is not date or type(day_b) is not date or day_a == day_b:
        raise ValueError("two_distinct_cairo_days_required")
    first = _one(folder_a, day_a)
    second = _one(folder_b, day_b)
    if first["word_sha256"] == second["word_sha256"]:
        raise ValueError("distinct_day_word_content_reused")
    rows = sorted((first, second), key=lambda x: x["day"])
    return {
        "status": VERDICT,
        "days": rows,
        "days_count": 2,
        "original_sources_per_day": 3,
        "local_integrity_verified": True,
        "attestations_are_self_reported_not_cryptographically_signed": True,
        "stage2_human_evidence_ready_for_separate_owner_acceptance": True,
        "production_delivery_approved": False,
        "email_sent": False,
        "scheduler_enabled": False,
        "storage_activated": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-a", type=Path, required=True)
    parser.add_argument("--day-a", type=date.fromisoformat, required=True)
    parser.add_argument("--folder-b", type=Path, required=True)
    parser.add_argument("--day-b", type=date.fromisoformat, required=True)
    p = parser.parse_args()
    try:
        verdict = verify_two_completed_days(
            p.folder_a, p.day_a, p.folder_b, p.day_b,
        )
    except Exception:
        # No local path, article body, or private encrypted evidence in logs.
        print(json.dumps({
            "status": "HOLD",
            "reason": "two_day_local_private_evidence_unverified",
            "production_delivery_approved": False,
        }))
        raise SystemExit(2) from None
    print(json.dumps(verdict, sort_keys=True))


if __name__ == "__main__":
    main()
