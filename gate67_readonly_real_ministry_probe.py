"""Read-only owner QA diagnostic on the SAME real Stage2 collector — no secrets.

This one-off branch-only diagnostic NEVER archives a plaintext Word,
never encrypts with a fake owner key, never sends SMTP, never alters sources,
never claims Stage2 human acceptance. Temporary Word/JPEG are deleted.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from docx import Document

from gate63_unified_mail_no_send import no_send_unified_mime_preflight
from unified_ministry_word import build_unified_word

CAIRO = ZoneInfo("Africa/Cairo")
_EXPECTED_SOURCES = {"hapi", "almasryalyoum", "mped-official"}


def verify_ephemeral_report(audit: dict, directory: Path, day) -> dict:
    """Safe redacted diagnostics; never log article text/URL/SHA/Word bytes."""
    if (audit.get("mode") != "stage2_ministry_unified_word_ephemeral_qa" or
            audit.get("target_date_cairo") != day.isoformat() or
            audit.get("email_sent") is not False or
            audit.get("scheduler_enabled") is not False or
            audit.get("private_storage_used") is not False or
            audit.get("source_added_to_production") is not False or
            audit.get("production_sources_changed") is not False or
            audit.get("keywords_changed") is not False or
            audit.get("final_report_published") is not False):
        raise ValueError("gate67_stage2_scope_or_privacy_mismatch")

    rows = audit.get("source_health")
    if (not isinstance(rows, list) or len(rows) != 3 or
            {x.get("feed_id") for x in rows if type(x) is dict} != _EXPECTED_SOURCES):
        raise ValueError("gate67_original_source_inventory_mismatch")

    safe = {
        "status": audit.get("status"),
        "date_cairo": day.isoformat(),
        "source_health": [
            {"id": x["feed_id"], "ok": x["status"] == "ok",
             "original_links": x["verified_links"]}
            for x in rows
        ],
        "all_sources_healthy": audit.get("all_sources_healthy"),
        "ministry_same_day": audit.get("official_same_day"),
        "ministry_pages_checked": audit.get("official_pages_checked"),
        "ministry_pagination_complete": audit.get("official_pagination_complete"),
        "rss_matching_on_day": audit.get("rss_matched_on_day"),
        "article_count": audit.get("selected_unique_articles"),
        "screenshots_verified": audit.get("screenshots_verified"),
        "word_created": audit.get("word_created"),
        "mime_no_send": False,
        "delivery_approved": False,
        "human_review": False,
    }
    # Do not return report text, original article URLs, SHA digests, images,
    # Word files, sender/recipient identities or private service names.
    words = sorted(directory.glob("RASD-Unified-*.docx"))
    if audit.get("status") == "HOLD":
        if words or audit.get("word_created") is not False:
            raise ValueError("gate67_hold_must_not_leave_word")
        safe["reason"] = "ORIGINAL_SOURCE_OR_DATE_OR_PROOF_HOLD"
        return safe
    if (audit.get("status") != "READY_QA_ONLY" or
            audit.get("all_sources_healthy") is not True or
            audit.get("coverage") != "HEALTHY" or
            len(words) != 1 or words[0].is_symlink() or
            words[0].name != f"RASD-Unified-{day.isoformat()}.docx" or
            audit.get("official_pagination_complete") is not True or
            audit.get("word_images_verified") is not True or
            audit.get("screenshots_missing") != 0 or
            not 1 <= audit["selected_unique_articles"] <= 15 or
            audit.get("screenshots_verified") != audit["selected_unique_articles"] or
            len(Document(words[0]).inline_shapes) != audit["selected_unique_articles"]):
        raise ValueError("gate67_real_word_or_original_screenshot_evidence_failed")

    mime = no_send_unified_mime_preflight(audit, words[0], day)
    if (mime["status"] != "UNIFIED_WORD_MIME_NO_SEND_PREFLIGHT_ONLY" or
            mime["article_count"] != audit["selected_unique_articles"] or
            mime["attachment_count"] != 1 or
            mime["smtp_used"] is not False or
            mime["email_sent"] is not False or
            mime["private_ledger_touched"] is not False or
            mime["production_delivery_approved"] is not False):
        raise ValueError("gate67_mime_no_send_integrity_failed")
    safe["mime_no_send"] = True
    safe["status"] = "REAL_SOURCES_EPHEMERAL_WORD_MIME_QA_NOT_OWNER_REVIEW"
    return safe


def main() -> None:
    now = datetime.now(CAIRO)
    day = now.date() - timedelta(days=1)
    try:
        with tempfile.TemporaryDirectory(prefix="rasd-g67-ephemeral-private-") as temp:
            root = Path(temp)
            audit = build_unified_word(
                Path("sources.json"), root, target_day=day, now=now,
            )
            result = verify_ephemeral_report(audit, root, day)
            # A real Word/image was never uploaded/published or exposed in logs.
            print(json.dumps(result, sort_keys=True), flush=True)
            if result["status"] != "REAL_SOURCES_EPHEMERAL_WORD_MIME_QA_NOT_OWNER_REVIEW":
                raise SystemExit(2)
    except SystemExit:
        raise
    except Exception:
        print(json.dumps({
            "status": "HOLD",
            "reason": "gate67_real_original_evidence_or_privacy_failed",
            "email_sent": False,
            "published": False,
            "human_review": False,
        }, sort_keys=True), flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
