"""Owner-controlled ONE-TIME social status Word mail test.

This transports a RASD-generated, explicitly UNVERIFIED social monitoring
status (zero verified posts). It is not Facebook ingestion, news delivery,
or approval to change production schedule/recipients.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from docx import Document

from daily_report import CAIRO, _rtl
from delivery_bridge import now_iso, reserve_entry
from rasd_four_reports_no_send import run_no_send
from scheduled_rasd import approved_report_copy, protected_credentials, send_one_word

TEST_KEY = hashlib.sha256(
    b"rasd-social-status-owner-single-cc-test-2026-11-09-v1").hexdigest()[:24]
WORKFLOW_REF = (
    "Hatem1984/RASD-Cloud-Monitor/.github/workflows/"
    "rasd-social-mail-owner-once.yml@refs/heads/main"
)
OWNER_CONFIRM = "RASD-SOCIAL-ONE-TIME-CC-TEST"
TEST_FILENAME = "RASD-Social-Hourly-EMAIL-TEST-UNVERIFIED.docx"


def _last_completed_daily_day(now: datetime):
    local = now.astimezone(CAIRO)
    return local.date() if local.hour >= 22 else local.date() - timedelta(days=1)


def make_social_test_word(directory: Path, now: datetime,
                          *, renderer=run_no_send) -> Path:
    """Reuse the EXISTING RASD four-report builder, select social hourly only.

    This pilot sends a status with 0 verified posts; a real post, real image or
    fabricated delivery receipt cannot be introduced via this transport test.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("naive_test_clock_hold")
    directory.mkdir(parents=True, exist_ok=True)
    draft = renderer(
        now=now, final_day=_last_completed_daily_day(now),
        output=directory / "rasd-source-preview", probe_web=False)
    social = draft.get("reports", {}).get("social-hourly", {})
    if (draft.get("status") != "REVIEW_ONLY_NO_SEND"
            or draft.get("email_sent") is not False
            or draft.get("social_live_posts_verified") != 0
            or social.get("items") != 0
            or not isinstance(social.get("path"), str)):
        raise RuntimeError("social_test_expected_zero_unverified_items_hold")
    original = Path(social["path"]).resolve(strict=True)
    if not original.is_relative_to((directory / "rasd-source-preview").resolve()):
        raise RuntimeError("untrusted_social_report_path_hold")
    doc = Document(original)
    if doc.inline_shapes:
        raise RuntimeError("social_test_must_not_contain_unverified_images")
    replacements = {
        "هذه نسخة معاينة بلا إرسال أو اعتماد إنتاجي.":
            "هذه نسخة اختبار إرسال بالبريد فقط؛ ليست تقرير رصد معتمدًا "
            "ولا دليلًا على غياب منشورات من المنصات.",
        "معاينة محلية غير مرسلة":
            "اختبار تسليم من نظام رصد — غير معتمد إنتاجيًا",
    }
    updated = set()
    text_paragraphs = list(doc.paragraphs)
    for section in doc.sections:
        text_paragraphs.extend(section.footer.paragraphs)
    for paragraph in text_paragraphs:
        for run in paragraph.runs:
            for before, after in replacements.items():
                if before in run.text:
                    run.text = run.text.replace(before, after)
                    updated.add(before)
    if updated != set(replacements):
        raise RuntimeError("social_test_word_label_replacement_hold")
    notice = doc.paragraphs[0].insert_paragraph_before(
        "اختبار إرسال تقرير السوشيال من رصد — لا توجد منشورات موثقة "
        "في بيانات الاختبار، وصلاحيات Facebook العامة غير معتمدة."
    )
    _rtl(notice)
    doc.core_properties.title = "رصد | اختبار تسليم تقرير حالة السوشيال"
    doc.core_properties.author = "RASD — SOCIAL DELIVERY TEST ONLY"
    output = directory / TEST_FILENAME
    doc.save(output)
    verified = Document(output)
    if (not 3000 <= output.stat().st_size <= 8_000_000
            or verified.inline_shapes
            or any("معاينة محلية غير مرسلة" in p.text
                   for section in verified.sections
                   for p in section.footer.paragraphs)
            or not any("اختبار إرسال تقرير السوشيال من رصد" in p.text
                       for p in verified.paragraphs)):
        raise RuntimeError("social_test_word_integrity_hold")
    return output


def require_manual_send_context(env: dict[str, str]) -> None:
    """Fail closed on PR/push/schedule, reruns, other actors or empty CC.

    Input approval is never printed and is valid only for this exact manual
    workflow. It does not authorize a change to ordinary RASD delivery.
    """
    exact = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
        "GITHUB_WORKFLOW_REF": WORKFLOW_REF,
        "GITHUB_RUN_ATTEMPT": "1",
        "RASD_SOCIAL_TEST_APPROVAL": OWNER_CONFIRM,
        "RASD_REPORT_CC_REQUIRED": "true",
    }
    if (any(env.get(k) != v for k, v in exact.items())
            or env.get("GITHUB_ACTOR", "").casefold() != "hatem1984"
            or re.fullmatch(r"[0-9]{1,25}", env.get("GITHUB_RUN_ID", "")) is None
            or not env.get("RASD_REPORT_CC", "").strip()):
        raise RuntimeError("social_mail_test_manual_approval_or_cc_hold")


def run(*, mode: str, now: datetime | None = None,
        directory: Path | None = None,
        environment: dict[str, str] | None = None,
        renderer=run_no_send, credentials=protected_credentials,
        transport=send_one_word) -> dict:
    """No-send is the default. Exactly one private CAS reservation before SMTP."""
    if mode not in {"dry_run_no_network", "send_once"}:
        raise ValueError("social_mail_test_unknown_mode")
    environment = os.environ if environment is None else environment
    if mode == "send_once":
        require_manual_send_context(environment)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("naive_test_clock_hold")
    if directory is None:
        raise ValueError("social_test_explicit_ephemeral_output_required")
    report = make_social_test_word(directory, current, renderer=renderer)
    baseline = {
        "mode": mode, "verified_social_posts": 0,
        "filename": report.name, "cc_requested": True,
        "primary_inbox_verified": False, "cc_inbox_verified": False,
        "production_schedule_changed": False,
    }
    if mode == "dry_run_no_network":
        return {**baseline, "status": "DRY_RUN_NO_NETWORK",
                "smtp_accepted": False, "private_cas_mutated": False}

    # Original production identity gates validate sender, approved primary
    # digest and pinned approved CC. The live CC is a protected SECRET here,
    # never the existing public Actions variable.
    sender, primary, password, ledger = credentials()
    copy = approved_report_copy(sender, primary)
    if not copy or not environment.get("RASD_REPORT_CC", "").strip():
        raise RuntimeError("social_mail_test_approved_cc_required_hold")

    # Distinct once-ever key. No 'interval_item' or social accepted-news kind:
    # existing daily/news reconciliations must NEVER count this transport QA.
    # Reusing the trusted private CAS prevents duplicate/uncertain SMTP retry.
    state, sha = ledger.read()
    reserved, action = reserve_entry(state, TEST_KEY, now_iso())
    if action != "reserved":
        return {**baseline, "status": "HOLD_TEST_ALREADY_RESERVED_OR_SENT",
                "smtp_accepted": False, "private_cas_mutated": False}
    reserved["entries"][TEST_KEY]["kind"] = "social_transport_test_only"
    ledger.write(reserved, sha)
    receipt = transport(
        report, sender=sender, recipient=primary, password=password,
        subject="رصد | اختبار إرسال تقرير السوشيال | حالة وصول بدون أخبار موثقة",
        key=TEST_KEY,
        body_text=(
            "هذه رسالة اختبار واحدة أنشأها نظام رصد تلقائيًا. "
            "المرفق تقرير حالة السوشيال غير المعتمد، دون منشورات موثقة. "
            "الهدف اختبار تسليم Word إلى المستلم الأساسي ونسخة CC المعتمدة، "
            "وليس إثبات نجاح جمع منشورات Facebook أو اكتمال التغطية.\n"
        ),
    )
    ledger.mark_smtp_accepted(TEST_KEY, receipt)
    return {**baseline, "status": "SMTP_ACCEPTED_NOT_INBOX_VERIFIED",
            "smtp_accepted": True, "private_cas_mutated": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="RASD social Word owner mail test")
    parser.add_argument("--mode", choices=("dry_run_no_network", "send_once"),
                        default="dry_run_no_network")
    opts = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rasd-social-mail-test-") as folder:
        result = run(mode=opts.mode, directory=Path(folder))
    # Never log addresses, login, password, token, private ledger or message ID.
    print("RASD_SOCIAL_MAIL_TEST=" + json.dumps(
        result, ensure_ascii=True, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
