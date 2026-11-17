"""Gate 13: manual, environment-protected screenshot-verified DOCX Gmail transport.

Never scheduled. Reuses Gate 11 manual-owner consent and the same PRIVATE
compare-and-swap delivery ledger, with a distinct per-Cairo-day report key.
SMTP acceptance is NOT a claim that the inbox delivered the message.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
from io import BytesIO
import json
import re
import smtplib
import tempfile
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from docx import Document

from daily_report import CAIRO
from cloud_proof_report import build_proof_report, word_images_match_capture_digests
from delivery_bridge import PrivateGitHubLedger, gmail_submit
from gate11_runner import credentials

WORKFLOW_REF = (
    "Hatem1984/RASD-Cloud-Monitor/.github/workflows/"
    "digest-mail-manual.yml@refs/heads/main"
)
MAX_ATTACHMENT_BYTES = 5_000_000


def report_identity(now: datetime) -> tuple[str, str]:
    if now.tzinfo is None:
        raise ValueError("naive_digest_timestamp")
    date = now.astimezone(CAIRO).date().isoformat()
    key = hashlib.sha256(("rasd-daily-report-v1:" + date).encode()).hexdigest()[:24]
    return date, key


def verify_word(word: Path, date: str, expected_images: int) -> bytes:
    """Verify the one Word attachment really contains screenshot evidence."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("invalid_report_date")
    if word.name != f"RASD-Daily-{date}.docx":
        raise ValueError("report_file_identity_mismatch")
    if not word.is_file():
        raise ValueError("report_attachment_missing")
    content = word.read_bytes()
    if not 3000 <= len(content) <= MAX_ATTACHMENT_BYTES:
        raise ValueError("report_attachment_size_invalid")
    if not content.startswith(b"PK"):
        raise ValueError("report_attachment_format_invalid")
    try:
        doc = Document(BytesIO(content))
        if (not doc.paragraphs or
                type(expected_images) is not int or expected_images < 1 or
                len(doc.inline_shapes) != expected_images):
            raise ValueError("report_screenshot_evidence_incomplete")
    except Exception:
        raise ValueError("report_attachment_invalid") from None
    return content


def build_digest_message(report: dict, date: str, key: str,
                         word: bytes, sender: str) -> EmailMessage:
    if not re.fullmatch(r"[^@\s]+@gmail\.com", sender, re.I):
        raise ValueError("invalid_gmail_sender")
    if not re.fullmatch(r"[0-9a-f]{24}", key):
        raise ValueError("invalid_digest_fingerprint")
    if report.get("email_sent") is not False or report.get("scheduler_enabled") is not False:
        raise ValueError("unexpected_report_side_effect")
    if report.get("private_state_used") is not False:
        raise ValueError("private_report_data_forbidden")
    if report.get("coverage") != "HEALTHY" or report.get("status") != "READY":
        raise ValueError("digest_final_evidence_required")
    if (type(report.get("articles")) is not int or
            not 1 <= report["articles"] <= 15 or
            report.get("screenshots_verified") != report["articles"] or
            report.get("screenshots_missing") != 0 or
            report.get("word_created") is not True):
        raise ValueError("digest_all_screenshots_required")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = sender
    msg["Subject"] = "رصد | التقرير الإخباري اليومي | " + date
    msg["Message-ID"] = f"<rasd-{key}@gmail.com>"
    msg["X-RASD-Digest-ID"] = key
    msg.set_content(
        "تقرير رصد الإخباري الصادر من مصادر RSS الأصلية المعتمدة.\n\n"
        f"اليوم بتوقيت القاهرة: {date}\n"
        f"حالة تغطية المصادر: {report['coverage']}\n"
        f"العناوين المطابقة: {report['articles']}\n\n"
        "المرفق الوحيد Word بصور موثقة من صفحات الناشرين. "
        "خلو التقرير من الأخبار لا يثبت خلو الإنترنت من أخبار الوزارة.\n"
        "تأكيد SMTP لا يعني التحقق من وصول الرسالة لصندوق الوارد.\n"
    )
    msg.add_attachment(
        word, maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"RASD-Daily-{date}.docx",
    )
    return msg


def deliver_digest(report: dict, *, date: str, key: str, word: Path,
                   sender: str, approved_recipient: str, app_password: str,
                   ledger: PrivateGitHubLedger,
                   smtp_factory=smtplib.SMTP_SSL) -> str:
    """One automatic SMTP attempt per Cairo day; uncertain result stays HOLD."""
    if not sender or sender != approved_recipient:
        raise ValueError("digest_recipient_mismatch")
    if report_identity(datetime.fromisoformat(date + "T12:00:00+03:00"))[1] != key:
        # Identity must be derived from the report day, never arbitrary input.
        raise ValueError("digest_date_identity_mismatch")
    attachment = verify_word(word, date, report.get("articles", 0))
    # Validate the EXACT bytes that would be submitted to Gmail.
    # Image counts alone can accept altered JPEGs or swaps between articles.
    receipts = report.get("entries")
    if (not isinstance(receipts, list) or
            len(receipts) != report.get("articles") or
            not word_images_match_capture_digests(BytesIO(attachment), receipts)):
        raise ValueError("digest_word_evidence_integrity_failed")
    message = build_digest_message(report, date, key, attachment, sender)
    action = ledger.reserve(key, sender)  # commits and re-reads BEFORE SMTP
    if action != "reserved":
        return action
    receipt = gmail_submit(message, sender, app_password, smtp_factory=smtp_factory)
    ledger.mark_smtp_accepted(key, receipt)
    return "smtp_accepted"


def run(*, config_path: Path = Path("sources.json"),
        fetch=None, capture=None, clock: datetime | None = None,
        generator=build_proof_report, mailer=deliver_digest,
        ledger_factory=PrivateGitHubLedger,
        smtp_factory=smtplib.SMTP_SSL) -> dict:
    # Fail before visiting publishers, private state or Gmail when unsafe.
    approved = credentials()
    import os
    if os.environ.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF:
        raise RuntimeError("digest_requires_dedicated_manual_workflow")
    now = datetime.now(timezone.utc) if clock is None else clock
    date, key = report_identity(now)

    # Read-only replay gate: check the PRIVATE receipt BEFORE fetching RSS,
    # launching Chromium, or generating attachments. Uncertain reservations
    # are not retried. The actual new-send path still uses the existing
    # atomic reserve + SHA readback inside deliver_digest (race safe).
    ledger = ledger_factory(approved["RASD_PRIVATE_LEDGER_TOKEN"])
    private_state, _ = ledger.read()
    account_digest = hashlib.sha256(
        approved["RASD_GMAIL_USER"].strip().casefold().encode("utf-8")
    ).hexdigest()
    if not hmac.compare_digest(account_digest, private_state["approved_recipient_sha256"]):
        raise RuntimeError("digest_private_recipient_mismatch")
    existing = private_state["entries"].get(key)
    if existing:
        status = ("already_accepted" if existing["status"] == "smtp_accepted"
                  else "manual_review_hold")
        return {
            "mode": "manual_daily_digest_send",
            "date_cairo": date,
            "articles": None,
            "coverage": "NOT_RESCANNED",
            "status": status,
            "smtp_accepted": False,
            "inbox_delivery_verified": False,
            "source_scan_skipped": True,
            "scheduler_enabled": False,
        }
    with tempfile.TemporaryDirectory(prefix="rasd-digest-") as temp:
        folder = Path(temp)
        options = {"now": now}
        if fetch is not None:
            options["fetch"] = fetch
        if capture is not None:
            options["capture"] = capture
        report = generator(config_path, folder, **options)
        # STOP before private state reservation and SMTP unless ALL pages
        # have genuine verified screenshots inside a single final Word file.
        if report.get("status") != "READY" or not report.get("word_created"):
            raise RuntimeError("digest_publisher_evidence_incomplete")
        status = mailer(
            report, date=date, key=key,
            word=folder / f"RASD-Daily-{date}.docx",
            sender=approved["RASD_GMAIL_USER"],
            approved_recipient=approved["RASD_APPROVED_RECIPIENT"],
            app_password=approved["RASD_GMAIL_APP_PASSWORD"],
            ledger=ledger, smtp_factory=smtp_factory,
        )
    if status not in {"smtp_accepted", "already_accepted", "manual_review_hold"}:
        raise RuntimeError("digest_unexpected_delivery_status")
    return {
        "mode": "manual_daily_digest_send",
        "date_cairo": date,
        "articles": report["articles"],
        "coverage": report["coverage"],
        "status": status,
        "smtp_accepted": status == "smtp_accepted",
        "inbox_delivery_verified": False,
        "source_scan_skipped": False,
        "scheduler_enabled": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("send",), required=True)
    parser.parse_args()
    try:
        print(json.dumps(run(), ensure_ascii=False), flush=True)
    except Exception:
        # Never echo Google/SMTP/approval configuration in public job logs.
        print("rasd_digest_failed_closed; check private ledger and Gmail Sent before new dispatch",
              flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
