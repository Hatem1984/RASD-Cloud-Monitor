"""Fail-closed operational verdict for a protected, manually-triggered Stage 2 Word QA.

The host workflow may succeed in collecting/encrypting a HOLD audit, but
that MUST NOT be confused with an accepted complete-day report. No network,
storage, Gmail, scheduling, publisher text, or crypto secrets are used here.
"""
from __future__ import annotations

from datetime import date, timedelta


def stage2_manual_machine_verdict(
    audit: dict,
    receipt: dict,
    *,
    requested_window: str,
    today_cairo: date,
) -> str:
    """Return READY_QA_ONLY, PARTIAL_QA_ONLY or HOLD; never human approval.

    The SHA-checked Word, actual private PDF render and encrypted owner-page
    bundle are validated upstream. We independently verify their safe
    redacted receipt so an audit-only HOLD cannot become a green workflow.
    """
    if requested_window not in ("yesterday", "today"):
        raise ValueError("manual_window_not_approved")
    if type(today_cairo) is not date:
        raise ValueError("manual_today_cairo_invalid")
    expected_day = today_cairo - timedelta(days=1 if requested_window == "yesterday" else 0)
    if audit.get("target_date_cairo") != expected_day.isoformat():
        raise ValueError("manual_window_audit_date_mismatch")
    if (audit.get("mode") != "stage2_ministry_unified_word_ephemeral_qa"
            or audit.get("email_sent") is not False
            or audit.get("scheduler_enabled") is not False
            or audit.get("final_report_published") is not False
            or audit.get("source_added_to_production") is not False
            or audit.get("production_sources_changed") is not False
            or audit.get("keywords_changed") is not False
            or audit.get("private_storage_used") is not False
            or audit.get("date_only_official_not_assigned_hour") is not True
            or audit.get("production_15_item_cap_intact") is not True):
        raise ValueError("manual_protected_scope_violation")
    if receipt.get("encrypted") is not True or receipt.get("plaintext_artifact") is not False:
        raise ValueError("manual_ciphertext_receipt_missing")
    # Explicit source/evidence HOLD is an accepted safety refusal, NEVER
    # an accepted report. The workflow must show a RED machine-acceptance run.
    if audit.get("status") != "READY_QA_ONLY":
        if (audit.get("status") != "HOLD"
                or receipt.get("owner_review_word_included") is not False
                or receipt.get("owner_review_pages_encrypted") is not False):
            raise ValueError("manual_hold_contains_word_or_bad_status")
        return "HOLD"
    count = audit.get("selected_unique_articles")
    if (type(count) is not int or not 1 <= count <= 15
            or audit.get("coverage") != "HEALTHY"
            or audit.get("all_sources_healthy") is not True
            or audit.get("official_pagination_complete") is not True
            or audit.get("word_created") is not True
            or audit.get("word_images_verified") is not True
            or audit.get("screenshots_verified") != count
            or audit.get("screenshots_missing") != 0
            or receipt.get("owner_review_word_included") is not True
            or receipt.get("owner_review_pages_encrypted") is not True
            or type(receipt.get("owner_review_page_count")) is not int
            or receipt["owner_review_page_count"] < 1
            or receipt.get("human_visual_review") is not False):
        raise ValueError("manual_ready_evidence_incomplete")
    # An incomplete calendar day can produce private QA evidence only.
    # No partial-day success may count towards two FULL distinct Cairo days.
    return "READY_QA_ONLY" if requested_window == "yesterday" else "PARTIAL_QA_ONLY"
