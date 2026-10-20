"""Gate68: one-shot OWNER-ACTOR read-only Stage2 ciphertext evidence capture.

A one-time QA branch, not production, mail, private key use or permission
to forge the owner's private interactive review. No report/article plaintext
or screenshot is uploaded or logged. Actual live publisher coverage required.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from gate43_owner_encrypted_review import pack_owner_review
from gate58_manual_acceptance import stage2_manual_machine_verdict
from gate65_owner_bound_mime_no_send import owner_bound_stage2_mime_check
from unified_ministry_word import build_unified_word
from word_render_audit import rendered_word_preflight

CAIRO = ZoneInfo("Africa/Cairo")
EXPECTED_CAIRO_DAY = date(2026, 10, 20)
EXPECTED_PREVIOUS_DAY = date(2026, 10, 19)
EXPECTED_MAIN_BASE = "4f914c779a4528a2b1df7681dc6baca91e3257ca"
EXPECTED_BRANCH = "refs/heads/gate68-one-shot-owner-encrypted-day19"


def validate_one_shot_scope(now: datetime, *, actor: str, ref: str,
                            original_main_base: str) -> date:
    """Never fabricate a past full reporting window or owner identity."""
    if (now.tzinfo is None or now.utcoffset() is None or
            now.astimezone(CAIRO).date() != EXPECTED_CAIRO_DAY or
            now.astimezone(CAIRO).date() - timedelta(days=1)
            != EXPECTED_PREVIOUS_DAY):
        raise ValueError("gate68_original_cairo_day_no_longer_in_safe_window")
    if (actor != "Hatem1984" or ref != EXPECTED_BRANCH
            or original_main_base != EXPECTED_MAIN_BASE):
        raise ValueError("gate68_authenticated_owner_and_base_required")
    return EXPECTED_PREVIOUS_DAY


def verify_cipher_only(envelope: Path) -> int:
    """Verify uploaded file contains ONLY the approved AES-GCM envelope."""
    data = json.loads(envelope.read_text(encoding="ascii"))
    if (type(data) is not dict or
            set(data) != {"format", "ciphertext", "nonce", "wrapped"} or
            data["format"] != "RASD_G43_OWNER_ENCRYPTED" or
            any(type(data[k]) is not str or not data[k]
                for k in ("ciphertext", "nonce", "wrapped"))):
        raise ValueError("gate68_ciphertext_envelope_not_exclusive")
    # No original publisher data, Word, JPEG or hashes are emitted.
    return envelope.stat().st_size


def diagnose_rendered_headline_coverage(word: Path) -> None:
    """Redacted counts by article index from SAME private rendered PDF only.

    This independently checks LibreOffice/Poppler extraction and prints no
    words, phrases, URLs, SHA fingerprints, PDF, Word or screenshots.
    Diagnostic NEVER changes main acceptance rules or emits artifacts.
    """
    import re
    from docx import Document
    from word_render_audit import _run, _arabic_headline_tokens

    try:
        with tempfile.TemporaryDirectory(prefix="rasd-g68-safe-pdf-diag-",
                                         dir=os.environ["RUNNER_TEMP"]) as t:
            root = Path(t)
            _run(["libreoffice", "-env:UserInstallation=" +
                  (root / "profile").as_uri(),
                  "--headless", "--convert-to", "pdf", "--outdir",
                  str(root), str(word.resolve())], timeout=100)
            pdfs = list(root.glob("*.pdf"))
            if len(pdfs) != 1:
                print("RASD_G68_HEADLINE_DIAG=PDF_COUNT_UNEXPECTED")
                return
            texts = {
                m: _arabic_headline_tokens(
                    _run(["pdftotext", "-" + m, str(pdfs[0]), "-"],
                         timeout=35).stdout,
                    pdf_extraction=True)
                for m in ("layout", "raw")
            }
            headings = [p.text for p in Document(word).paragraphs
                        if re.match(r"^\\s*\\d{1,2}\\.\\s+", p.text)]
            results = []
            for index, original in enumerate(headings, 1):
                words = _arabic_headline_tokens(original)
                results.append({
                    "index": index, "expected_token_count": len(words),
                    "missing_layout_count": len(words - texts["layout"]),
                    "missing_raw_count": len(words - texts["raw"]),
                })
            print("RASD_G68_HEADLINE_DIAG_COUNTS=" +
                  json.dumps(results, sort_keys=True), flush=True)
    except Exception:
        print("RASD_G68_HEADLINE_DIAG=UNAVAILABLE", flush=True)


def run_one_shot() -> None:
    now = datetime.now(CAIRO)
    target_day = validate_one_shot_scope(
        now,
        actor=os.environ.get("GITHUB_ACTOR", ""),
        ref=os.environ.get("GITHUB_REF", ""),
        original_main_base=os.environ.get("RASD_GATE68_BASE", ""),
    )
    artifact = Path(os.environ["RUNNER_TEMP"]) / "rasd-g43-owner-encrypted.json"
    if artifact.exists():
        raise ValueError("gate68_existing_owner_artifact_forbidden")

    with tempfile.TemporaryDirectory(prefix="rasd-g68-private-",
                                     dir=os.environ["RUNNER_TEMP"]) as td:
        folder = Path(td)
        report_dir = folder / "report"
        report_dir.mkdir()
        print("RASD_G68_STAGE=ORIGINAL_COLLECTOR_START", flush=True)
        audit = build_unified_word(
            Path("sources.json"), report_dir, target_day=target_day, now=now,
        )
        # Safe public audit: known status, source ID/health, counts,
        # allowlisted code names; no original article content or file hashes.
        print("RASD_G68_COLLECTOR_REDacted=" + json.dumps({
            "status": audit.get("status"),
            "health": [{"source": r.get("feed_id"), "ok": r.get("status") == "ok"}
                       for r in audit.get("source_health", [])],
            "official_on_day": audit.get("official_same_day"),
            "article_count": audit.get("selected_unique_articles"),
            "verified_screenshots": audit.get("screenshots_verified"),
            "failure_labels": sorted(audit.get("failures", {}).keys()),
            "word_created": audit.get("word_created"),
        }, sort_keys=True), flush=True)
        if (audit.get("status") not in ("READY_QA_ONLY", "HOLD")
                or audit.get("email_sent") is not False
                or audit.get("scheduler_enabled") is not False
                or audit.get("private_storage_used") is not False
                or audit.get("source_added_to_production") is not False
                or audit.get("production_sources_changed") is not False
                or audit.get("keywords_changed") is not False
                or audit.get("final_report_published") is not False):
            raise ValueError("gate68_original_source_or_privacy_failure")

        rendered = False
        pages = folder / "rendered-pages"
        if audit["status"] == "READY_QA_ONLY":
            words = list(report_dir.glob("RASD-Unified-*.docx"))
            if len(words) != 1:
                raise ValueError("gate68_original_word_missing_or_ambiguous")
            print("RASD_G68_STAGE=RENDER_ORIGINAL_WORD_PAGES", flush=True)
            try:
                result = rendered_word_preflight(
                    words[0],
                    expected_articles=audit["selected_unique_articles"],
                    review_pages_dir=pages,
                )
            except Exception as exc:
                # Public logs may contain only predefined render failure
                # CODES, never PDF extracted Arabic original article text,
                # paths, document text, screenshots, or subprocess stderr.
                approved = {
                    "qa_original_publisher_image_count_mismatch",
                    "qa_publisher_picture_too_narrow_or_outside_page",
                    "qa_rendered_arabic_text_layer_missing",
                    "qa_rendered_original_headline_missing",
                    "qa_original_report_headline_count_mismatch",
                    "qa_offline_pdf_render_failed",
                    "qa_rendered_page_count_invalid",
                    "qa_page_raster_too_small",
                    "qa_blank_or_unreadable_rendered_page",
                    "qa_review_pages_destination_already_exists",
                }
                code = str(exc) if type(exc) is ValueError and str(exc) in approved else "RENDER_GENERIC_HOLD"
                print("RASD_G68_REDACTED_RENDER_FAILURE=" + code, flush=True)
                if code == "qa_rendered_original_headline_missing":
                    diagnose_rendered_headline_coverage(words[0])
                raise
            if (result.get("status") != "RENDER_CHECK_PASSED_NOT_HUMAN_REVIEW"
                    or result.get("private_owner_review_pages_staged") is not True
                    or result.get("rendered_page_count", 0) < 1):
                raise ValueError("gate68_original_word_render_hold")
            rendered = True

        # Encrypt original rendered pages and Word BEFORE MIME inspection:
        # exact same original Word SHA recorded inside owner's ciphertext.
        print("RASD_G68_STAGE=ENCRYPT_OWNER_WORD_AND_PAGES", flush=True)
        receipt = pack_owner_review(
            report_dir, audit, artifact,
            render_passed=rendered,
            review_pages_dir=pages if rendered else None,
        )
        verify_cipher_only(artifact)
        print("RASD_G68_STAGE=CIPHERTEXT_PACKED_EXCLUSIVE", flush=True)
        verdict = stage2_manual_machine_verdict(
            audit, receipt, requested_window="yesterday",
            today_cairo=now.date(),
        )
        print("RASD_G68_STAGE=BOUND_MIME_NO_SEND_VALIDATION", flush=True)
        mime = owner_bound_stage2_mime_check(
            audit, report_dir, owner_receipt=receipt,
            requested_window="yesterday", today_cairo=now.date(),
        )
        summary = {
            "status": verdict,
            "target_date_cairo": target_day.isoformat(),
            "source_health": [
                {"source": r.get("feed_id"), "status": r.get("status")}
                for r in audit.get("source_health", [])
            ],
            "sources_healthy": audit.get("all_sources_healthy"),
            "article_count": audit.get("selected_unique_articles"),
            "original_screenshots": audit.get("screenshots_verified"),
            "word_in_owner_ciphertext": receipt["owner_review_word_included"],
            "pages_in_owner_ciphertext": receipt["owner_review_page_count"],
            "mime_no_send_qa": mime["status"],
            "human_review": False,
            "gmail_sent": False, "r2_used": False,
            "scheduler_enabled": False,
            "production_approved": False,
        }
        print("RASD_GATE68_ENCRYPTED_OWNER_AUDIT=" +
              json.dumps(summary, sort_keys=True), flush=True)
        if (verdict != "READY_QA_ONLY"
                or mime["status"] != "UNIFIED_WORD_MIME_NO_SEND_QA_ONLY"
                or not rendered):
            raise ValueError("gate68_original_report_hold_not_owner_accepted")
    # The temp Word/photos/rendered private pages are irreversibly cleaned up.
    # The ONLY retained runner output is AES-GCM ciphertext for owner download.


if __name__ == "__main__":
    try:
        run_one_shot()
    except Exception as exc:
        # No exception traceback may include publisher text, file path or SHA.
        print("::error::RASD_GATE68_FAIL_CLOSED_NO_PRODUCTION_APPROVAL")
        raise SystemExit(2) from None
