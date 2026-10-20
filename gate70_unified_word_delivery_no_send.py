"""Gate70: separate 3-source unified Word from legacy RSS digest identity.

Dry-run ONLY. This module prepares a checkable strict transport contract for
a future approved manual Gmail pipeline. It never opens SMTP/HTTP/ledger,
does not accept a human approval as automatically proven, and never sends.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date
from pathlib import Path

from gate63_unified_mail_no_send import no_send_unified_mime_preflight

SHA = re.compile(r"[0-9a-f]{64}\Z")


def unified_delivery_key(day: date) -> str:
    """Domain-separate legacy RASD-Daily email reservations from 3-source Word."""
    if type(day) is not date:
        raise ValueError("gate70_invalid_cairo_day")
    return hashlib.sha256(
        ("rasd-unified-3-original-sources-word-v1:" + day.isoformat()).encode()
    ).hexdigest()[:24]


def no_send_unified_delivery_contract(
    audit: dict, word: Path, *, cairo_day: date,
    owner_packed_sha256: str,
) -> dict:
    """Verify source audit+real Word+private package SHA, NEVER authorize send.

    The digest must come from the existing encrypted owner audit/receipt
    (Gate65); an operator-supplied or unauthenticated digest alone does not
    prove owner visual approval. All real delivery stays disabled.
    """
    if (type(owner_packed_sha256) is not str or
            SHA.fullmatch(owner_packed_sha256) is None):
        raise ValueError("gate70_packed_word_sha_missing")
    # The existing gate63 checks the ACTUAL attachment bytes, 3 original
    # source statuses, completed Cairo day, all screenshots and DOCX media.
    result = no_send_unified_mime_preflight(audit, Path(word), cairo_day)
    if result.get("status") != "UNIFIED_WORD_MIME_NO_SEND_PREFLIGHT_ONLY":
        raise ValueError("gate70_source_or_attachment_qualification_failed")
    if not hmac.compare_digest(
        result.get("attachment_sha256", ""), owner_packed_sha256
    ):
        raise ValueError("gate70_unified_word_mismatch_owner_ciphertext")
    if (result.get("smtp_used") is not False or
            result.get("email_sent") is not False or
            result.get("private_ledger_touched") is not False or
            result.get("production_delivery_approved") is not False or
            result.get("gmail_authenticated") is not False or
            result.get("human_review_inferred") is not False):
        raise ValueError("gate70_no_send_invariants_failed")
    # Return only predictable non-personal metadata; not original Word hash,
    # report text, URL or MIME bytes, owner key, recipient or server response.
    return {
        "status": "UNIFIED_WORD_DELIVERY_CONTRACT_NO_SEND_ONLY",
        "date_cairo": cairo_day.isoformat(),
        "delivery_id": unified_delivery_key(cairo_day),
        "attachment_count": 1,
        "original_sources_verified": result["original_source_count"],
        "articles": result["article_count"],
        "packed_original_word_identity_verified": True,
        "mail_transport_implemented": False,
        "smtp_used": False,
        "private_ledger_touched": False,
        "gmail_authenticated": False,
        "owner_human_review_automated": False,
        "email_sent": False,
        "r2_used": False,
        "scheduler_enabled": False,
        "production_delivery_approved": False,
    }


def preview_legacy_key_conflict(day: date) -> bool:
    """Regression guard: new report ledger slot must NEVER equal old digest."""
    from digest_mailer import report_identity
    from datetime import datetime
    from zoneinfo import ZoneInfo
    old_key = report_identity(
        datetime(day.year, day.month, day.day, 12, 0,
                 tzinfo=ZoneInfo("Africa/Cairo"))
    )[1]
    return unified_delivery_key(day) == old_key
