"""Gate65 — bind the EXACT AES-GCM owner-packed Word to no-send MIME QA.

Only reused inside the existing manual, no-Gmail Stage2 workflow.
Never opens a socket, sends SMTP, touches ledger, uploads Word or approves
human review. Report is already RSA/AES-GCM encrypted BEFORE this check.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

from gate64_stage2_live_mime_no_send import stage2_live_no_send_mime_check

_HEX = re.compile(r"[0-9a-f]{64}\Z")


def owner_bound_stage2_mime_check(
    audit: dict, private_report_dir: Path, *,
    owner_receipt: dict, requested_window: str, today_cairo: date,
) -> dict:
    """Fail closed if encrypted owner Word differs from MIME's source Word."""
    if type(owner_receipt) is not dict or not all((
        owner_receipt.get("encrypted") is True,
        owner_receipt.get("plaintext_artifact") is False,
        owner_receipt.get("human_visual_review") is False,
        owner_receipt.get("email_sent") is False,
    )):
        raise ValueError("gate65_owner_encrypted_receipt_invalid")
    if type(audit) is not dict:
        raise ValueError("gate65_missing_source_audit")
    expected = owner_receipt.get("owner_packed_word_sha256")
    ready = audit.get("status") == "READY_QA_ONLY"
    root = Path(private_report_dir)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("gate65_private_word_directory_invalid")
    actual = sorted(root.glob("RASD-Unified-*.docx"))
    if ready:
        if (owner_receipt.get("owner_review_word_included") is not True or
                len(actual) != 1 or actual[0].is_symlink() or
                type(expected) is not str or not _HEX.fullmatch(expected)):
            raise ValueError("gate65_packed_word_sha_missing_or_ambiguous")

        def verify_same_word_bytes() -> None:
            # Compare against hash of SAME Word bytes that were actually
            # embedded in the owner-only encrypted ZIP.
            if hashlib.sha256(actual[0].read_bytes()).hexdigest() != expected:
                raise ValueError("gate65_owner_packed_word_sha256_mismatch")

        verify_same_word_bytes()
    elif audit.get("status") == "HOLD":
        if (owner_receipt.get("owner_review_word_included") is not False or
                expected is not None or actual):
            raise ValueError("gate65_hold_contains_packed_word_claim")
    else:
        raise ValueError("gate65_unrecognized_source_verdict")

    result = stage2_live_no_send_mime_check(
        audit, root, requested_window=requested_window,
        today_cairo=today_cairo,
    )
    if ready:
        # A mutation between owner encryption and in-memory MIME validation
        # must not count as a successfully bound report, even if the DOCX
        # remains syntactically valid and contains the same number of images.
        verify_same_word_bytes()
        if requested_window == "yesterday" and (
            result.get("status") != "UNIFIED_WORD_MIME_NO_SEND_QA_ONLY" or
            result.get("mime_rehearsed") is not True
        ):
            raise ValueError("gate65_expected_full_day_mime_not_verified")
    elif result.get("mime_rehearsed") is not False:
        raise ValueError("gate65_hold_mime_must_be_skipped")
    if (result.get("smtp_used") is not False or
            result.get("email_sent") is not False or
            result.get("production_delivery_approved") is not False):
        raise ValueError("gate65_no_send_privacy_invariant_failed")
    return result
