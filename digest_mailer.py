"""Gate 13: manual, environment-protected daily DOCX + PDF Gmail transport.

Never scheduled. Reuses Gate 11 manual-owner consent and the same PRIVATE
compare-and-swap delivery ledger, with a distinct per-Cairo-day report key.
SMTP acceptance is NOT a claim that the inbox delivered the message.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import smtplib
import tempfile
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from daily_report import CAIRO, generate
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


def verify_documents(word: Path, pdf: Path, date: str) -> tuple[bytes, bytes]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("invalid_report_date")
    if word.name != f"RASD-Daily-{date}.docx" or pdf.name != f"RASD-Daily-{date}.pdf":
        raise ValueError("report_file_identity_mismatch")
    if not word.is_file() or not pdf.is_file():
        raise ValueError("report_attachments_missing")
    if not (3000 <= word.stat().st_size <= MAX_ATTACHMENT_BYTES
            and 3000 <= pdf.stat().st_size <= MAX_ATTACHMENT_BYTES):
        raise ValueError("report_attachment_size_invalid")
    docx_bytes, pdf_bytes = word.read_bytes(), pdf.read_bytes()
    if not docx_bytes.startswith(b"PK") or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("report_attachment_format_invalid")
    try:
        if not Document(word).paragraphs or not PdfReader(pdf).pages:
            raise ValueError("report_attachment_empty")
    except Exception:
        raise ValueError("report_attachment_invalid") from None
    return docx_bytes, pdf_bytes


def build_digest_message(report: dict, date: str, key: str,
                         word: bytes, pdf: bytes, sender: str) -> EmailMessage:
    if not re.fullmatch(r"[^@\s]+@gmail\.com", sender, re.I):
        raise ValueError("invalid_gmail_sender")
    if not re.fullmatch(r"[0-9a-f]{24}", key):
        raise ValueError("invalid_digest_fingerprint")
    if report.get("email_sent") is not False or report.get("scheduler_enabled") is not False:
        raise ValueError("unexpected_report_side_effect")
    if report.get("private_state_used") is not False:
        raise ValueError("private_report_data_forbidden")
    if report.get("coverage") not in {"HEALTHY", "DEGRADED"}:
        raise ValueError("unverified_report_coverage")
    if (not isinstance(report.get("articles"), int)
            or not 0 <= report["articles"] <= 15):
        raise ValueError("unverified_report_item_count")
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
        "النسختان المرفقتان Word وPDF. "
        "خلو التقرير من الأخبار لا يثبت خلو الإنترنت من أخبار الوزارة.\n"
        "تأكيد SMTP لا يعني التحقق من وصول الرسالة لصندوق الوارد.\n"
    )
    msg.add_attachment(
        word, maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"RASD-Daily-{date}.docx",
    )
    msg.add_attachment(
        pdf, maintype="application", subtype="pdf",
        filename=f"RASD-Daily-{date}.pdf",
    )
    return msg


def deliver_digest(report: dict, *, date: str, key: str, word: Path, pdf: Path,
                   sender: str, approved_recipient: str, app_password: str,
                   ledger: PrivateGitHubLedger,
                   smtp_factory=smtplib.SMTP_SSL) -> str:
    """One automatic SMTP attempt per Cairo day; uncertain result stays HOLD."""
    if not sender or sender != approved_recipient:
        raise ValueError("digest_recipient_mismatch")
    if report_identity(datetime.fromisoformat(date + "T12:00:00+03:00"))[1] != key:
        # Identity must be derived from the report day, never arbitrary input.
        raise ValueError("digest_date_identity_mismatch")
    attachments = verify_documents(word, pdf, date)
    message = build_digest_message(report, date, key, *attachments, sender)
    action = ledger.reserve(key, sender)  # commits and re-reads BEFORE SMTP
    if action != "reserved":
        return action
    receipt = gmail_submit(message, sender, app_password, smtp_factory=smtp_factory)
    ledger.mark_smtp_accepted(key, receipt)
    return "smtp_accepted"


def run(*, config_path: Path = Path("sources.json"),
        fetch=None, clock: datetime | None = None,
        generator=generate, mailer=deliver_digest,
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
        report = generator(config_path, folder, **options)
        if not report.get("word_created") or not report.get("pdf_created"):
            raise RuntimeError("digest_report_not_generated")
        status = mailer(
            report, date=date, key=key,
            word=folder / f"RASD-Daily-{date}.docx",
            pdf=folder / f"RASD-Daily-{date}.pdf",
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
