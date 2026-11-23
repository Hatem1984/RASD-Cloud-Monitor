"""Owner-authorized PRIVATE daily Sent archive diagnosis: READ ONLY.

Runs solely in the protected one-off owner workflow with scoped credential
secrets. It reads the existing production CAS and Gmail Sent, never writes
ledger state or attempts SMTP. Public log output contains ONLY fixed stage
and error-code values and dates; no mailbox IDs, articles, file names, links,
JWTs, Message-IDs, JPEG hashes, or MIME.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from daily_sent_consolidator import consolidate_sent_words
from scheduled_rasd import (
    protected_credentials, news_for_rollup, safe_scheduled_hold_reason,
    approved_report_copy,
)


def diagnose() -> dict:
    sender, recipient, password, ledger = protected_credentials()
    config = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    state, _ = ledger.read()
    observed = {}
    for day in ("2026-11-21", "2026-11-22"):
        phase = "select_accepted_sent_articles"
        try:
            stories = news_for_rollup(state, day, config)
            if not stories:
                observed[day] = "NO_ACCEPTED_ITEMS"
                print("RASD_READONLY_DAILY=" + json.dumps(
                    {"day": day, "phase": phase, "status": "HOLD_NO_ITEMS",
                     "smtp_attempted": False, "ledger_written": False},
                    sort_keys=True), flush=True)
                continue
            phase = "original_gmail_sent_imap_to_verified_word"
            with tempfile.TemporaryDirectory(prefix="rasd-owner-readonly-") as temp:
                doc, originals = consolidate_sent_words(
                    stories, state, Path(temp),
                    sender=sender, recipient=recipient, app_password=password,
                    approved_copy=approved_report_copy(sender, recipient),
                    title="رصد | اختبار قراءة Sent فقط — بدون إرسال",
                    start="22:00 القاهرة اليوم السابق",
                    end=day + " 22:00 القاهرة", config=config,
                )
                from docx import Document
                if len(Document(doc).inline_shapes) != len(stories) or (
                        len(originals) != len(stories)):
                    raise RuntimeError("daily_consolidation_missing_original_images")
            observed[day] = "VERIFIED_READ_ONLY"
            print("RASD_READONLY_DAILY=" + json.dumps(
                {"day": day, "phase": "word_verified", "status": "PASS",
                 "smtp_attempted": False, "ledger_written": False},
                sort_keys=True), flush=True)
        except Exception as exc:
            observed[day] = "HOLD"
            print("RASD_READONLY_DAILY=" + json.dumps(
                {"day": day, "phase": phase, "status": "HOLD",
                 "code": safe_scheduled_hold_reason(exc),
                 "smtp_attempted": False, "ledger_written": False},
                sort_keys=True), flush=True)
    return observed


if __name__ == "__main__":
    diagnose()
