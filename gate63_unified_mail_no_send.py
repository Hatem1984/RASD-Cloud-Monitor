"""Stage63: strict NO-SEND MIME rehearsal for the NEW unified Ministry Word.

Only in-memory EmailMessage with reserved .invalid sample address.
No credential lookup, private ledger, SMTP, transport, GitHub state, or upload.
This is NOT authorization to send, and does NOT replace original capture SHA
proof or a real owner's private review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

from docx import Document

from gate61_owner_private_visual_review import CAIRO

_EXPECTED = {"hapi", "almasryalyoum", "mped-official"}
_PLACEHOLDER = "rasd-no-send-preflight@example.invalid"
_MAX_WORD = 5_000_000
_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def no_send_unified_mime_preflight(audit: dict, word: Path,
                                  target_day: date) -> dict:
    if type(target_day) is not date or target_day >= datetime.now(CAIRO).date():
        raise ValueError("unified_mail_preflight_requires_complete_cairo_day")
    if type(audit) is not dict or audit.get("target_date_cairo") != target_day.isoformat():
        raise ValueError("unified_mail_preflight_audit_day_mismatch")
    if (audit.get("mode") != "stage2_ministry_unified_word_ephemeral_qa" or
            audit.get("status") != "READY_QA_ONLY" or
            audit.get("coverage") != "HEALTHY" or
            audit.get("all_sources_healthy") is not True or
            audit.get("word_created") is not True or
            audit.get("word_images_verified") is not True or
            audit.get("official_pagination_complete") is not True or
            audit.get("production_15_item_cap_intact") is not True or
            audit.get("email_sent") is not False or
            audit.get("scheduler_enabled") is not False or
            audit.get("final_report_published") is not False or
            audit.get("private_storage_used") is not False or
            audit.get("source_added_to_production") is not False or
            audit.get("production_sources_changed") is not False or
            audit.get("keywords_changed") is not False):
        raise ValueError("unified_mail_preflight_stage2_not_qualified")
    count = audit.get("selected_unique_articles")
    if (type(count) is not int or not 1 <= count <= 15 or
            audit.get("screenshots_verified") != count or
            audit.get("screenshots_missing") != 0 or
            audit.get("rss_source_count") != 2 or
            audit.get("official_source_count") != 1):
        raise ValueError("unified_mail_preflight_article_evidence_incomplete")
    health = audit.get("source_health")
    if (type(health) is not list or len(health) != 3 or
            {r.get("feed_id") for r in health if type(r) is dict} != _EXPECTED or
            any(type(r) is not dict or r.get("status") != "ok" or
                type(r.get("verified_links")) is not int or
                r["verified_links"] < 0 or
                (r.get("feed_id") == "mped-official" and
                 r["verified_links"] < 1) for r in health)):
        raise ValueError("unified_mail_preflight_original_source_incomplete")
    word = Path(word)
    if (word.name != f"RASD-Unified-{target_day.isoformat()}.docx" or
            not word.is_file() or word.is_symlink() or
            not 3000 <= word.stat().st_size <= _MAX_WORD):
        raise ValueError("unified_mail_preflight_word_invalid")
    body = word.read_bytes()
    if not body.startswith(b"PK"):
        raise ValueError("unified_mail_preflight_word_not_docx")
    try:
        doc = Document(BytesIO(body))
        if not doc.paragraphs or len(doc.inline_shapes) != count:
            raise ValueError("unified_mail_preflight_word_picture_count")
    except Exception:
        raise ValueError("unified_mail_preflight_word_invalid") from None

    # Never include a real address or Gmail token in this preflight. MIME is
    # created only in local RAM and never handed to a send() or API.
    msg = EmailMessage()
    msg["From"] = _PLACEHOLDER
    msg["To"] = _PLACEHOLDER
    msg["Subject"] = "رصد | معاينة المرفق الموحد فقط | " + target_day.isoformat()
    msg["X-RASD-Preview-Only"] = "NO-SEND-NO-GMAIL"
    msg.set_content(
        "معاينة محلية فقط؛ لا إرسال. تقرير وزارة التخطيط الموحد."
        f"\nتاريخ القاهرة المكتمل: {target_day.isoformat()}"
        f"\nعدد الأخبار الموثقة: {count}\n"
        "تحتاج قنوات الإنتاج لاعتماد منفصل.\n"
    )
    msg.add_attachment(
        body, maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=word.name,
    )
    # Verify precisely the MIME attachment bytes, independent of filename.
    attachments = list(msg.iter_attachments())
    if (len(attachments) != 1 or
            attachments[0].get_content_type() != _MIME or
            attachments[0].get_filename() != word.name or
            attachments[0].get_content() != body or
            msg.get("X-RASD-Preview-Only") != "NO-SEND-NO-GMAIL" or
            msg["To"] != _PLACEHOLDER or msg["From"] != _PLACEHOLDER):
        raise RuntimeError("unified_mail_preflight_mime_integrity_failed")
    return {
        "status": "UNIFIED_WORD_MIME_NO_SEND_PREFLIGHT_ONLY",
        "date_cairo": target_day.isoformat(),
        "article_count": count,
        "original_source_count": 3,
        "attachment_count": 1,
        "attachment_sha256": hashlib.sha256(body).hexdigest(),
        "attachment_bytes": len(body),
        "smtp_used": False,
        "private_ledger_touched": False,
        "gmail_authenticated": False,
        "human_review_inferred": False,
        "production_delivery_approved": False,
        "email_sent": False,
        "scheduler_enabled": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--word", type=Path, required=True)
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    options = parser.parse_args()
    try:
        data = json.loads(options.audit.read_text(encoding="utf-8"))
        result = no_send_unified_mime_preflight(data, options.word, options.day)
    except Exception:
        print(json.dumps({"status": "HOLD", "email_sent": False,
                          "reason": "unified_mime_no_send_preflight_failed"}))
        raise SystemExit(2) from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
