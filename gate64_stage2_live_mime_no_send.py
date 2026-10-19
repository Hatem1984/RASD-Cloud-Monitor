"""Gate64: rehearse Gmail-format MIME for the ACTUAL unified Stage2 Word.

This function is called only by the existing owner-manual, NO-GMAIL,
owner-encrypted QA workflow. No SMTP, recipient, private ledger, network,
publication or customer data. It never converts a machine QA pass into an
owner visual-review approval or production authorization.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from gate63_unified_mail_no_send import no_send_unified_mime_preflight


def stage2_live_no_send_mime_check(
    audit: dict, private_report_dir: Path, *,
    requested_window: str, today_cairo: date,
) -> dict:
    """Fail closed on bad report identity; skip only verified HOLD/partial."""
    if requested_window not in ("yesterday", "today"):
        raise ValueError("gate64_invalid_manual_window")
    if type(today_cairo) is not date:
        raise ValueError("gate64_invalid_cairo_clock")
    if type(audit) is not dict:
        raise ValueError("gate64_missing_source_audit")
    day = today_cairo - timedelta(days=(requested_window == "yesterday"))
    if (audit.get("mode") != "stage2_ministry_unified_word_ephemeral_qa"
            or audit.get("target_date_cairo") != day.isoformat()
            or audit.get("email_sent") is not False
            or audit.get("scheduler_enabled") is not False
            or audit.get("source_added_to_production") is not False
            or audit.get("private_storage_used") is not False):
        raise ValueError("gate64_source_day_or_safety_mismatch")

    root = Path(private_report_dir)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("gate64_private_word_directory_missing")
    words = sorted(root.glob("RASD-Unified-*.docx"))
    if any(w.is_symlink() for w in words):
        raise ValueError("gate64_private_word_symlink_forbidden")

    if audit.get("status") == "HOLD":
        if words or audit.get("word_created") is not False:
            raise ValueError("gate64_hold_with_unapproved_word")
        return {
            "status": "SKIPPED_SOURCE_OR_PROOF_HOLD",
            "mime_rehearsed": False, "smtp_used": False,
            "email_sent": False, "production_delivery_approved": False,
        }
    if audit.get("status") != "READY_QA_ONLY" or len(words) != 1:
        raise ValueError("gate64_ready_word_missing_or_ambiguous")
    if words[0].name != f"RASD-Unified-{day.isoformat()}.docx":
        raise ValueError("gate64_unified_word_day_identity_mismatch")
    if requested_window == "today":
        return {
            "status": "SKIPPED_PARTIAL_CAIRO_DAY",
            "mime_rehearsed": False, "smtp_used": False,
            "email_sent": False, "production_delivery_approved": False,
        }

    result = no_send_unified_mime_preflight(audit, words[0], day)
    if (result.get("status") != "UNIFIED_WORD_MIME_NO_SEND_PREFLIGHT_ONLY"
            or result.get("attachment_count") != 1
            or result.get("article_count") != audit.get("selected_unique_articles")
            or result.get("original_source_count") != 3
            or result.get("date_cairo") != day.isoformat()
            or result.get("smtp_used") is not False
            or result.get("email_sent") is not False
            or result.get("private_ledger_touched") is not False
            or result.get("gmail_authenticated") is not False
            or result.get("production_delivery_approved") is not False
            or result.get("human_review_inferred") is not False
            or result.get("scheduler_enabled") is not False):
        raise ValueError("gate64_unified_mime_invariants_failed")
    # No original headline, JPEG, DOCX bytes, recipient, private SHA, or
    # unencrypted MIME serialized to public Action logs or summaries.
    return {
        "status": "UNIFIED_WORD_MIME_NO_SEND_QA_ONLY",
        "mime_rehearsed": True, "attachment_count": 1,
        "article_count": result["article_count"], "original_source_count": 3,
        "smtp_used": False, "email_sent": False,
        "production_delivery_approved": False,
    }
