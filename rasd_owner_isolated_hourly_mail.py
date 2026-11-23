"""Strict owner-only SMTP test using REAL RASD Word code; never Ministry.

Protected one-off, no production ledger token, no production CAS or schedule.
The actual protected To address must match the pinned owner-personal digest;
Cc/Bcc and SMTP envelope are checked immediately BEFORE any send. One fresh
completed Cairo hour, genuine original publisher photos or a truthful zero/
image-HOLD Word. A unique test Message-ID is checked in Gmail Sent read-only
before sending; a failed/uncertain SMTP operation is NEVER retried.
No original headlines, email addresses or secrets leave the protected job log.
"""
from __future__ import annotations

import hashlib
import imaplib
import json
import os
import re
import ssl
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

from docx import Document
from cloud_proof_report import word_images_match_capture_digests
from daily_report import cairo_display_time
from rasd_strict_hourly_ten_source_gate import (
    audit_fresh_distinct_sources, last_completed_hour,
)
from rasd_hourly_delivery import hourly_period
from daily_sent_consolidator import sent_mailbox
import scheduled_rasd as worker

# Exact SHA256 of the single verified owner's personal Inbox address.
# No plaintext address, production email destination or additional copy.
PERSONAL_OWNER_SHA256 = "2cc074fcdbbbdc7506a9bcf36f4cea72921a1daab6b31bc6f0b788578ec595b2"
CAIRO = ZoneInfo("Africa/Cairo")


def require_isolated_scope(env: dict) -> tuple[str, str, str, str]:
    if any(env.get(k) != "false" for k in (
            "RASD_AUTOMATION_ENABLED", "RASD_HOURLY_REPORTS_ENABLED",
            "RASD_DAILY_VOLUME_DELIVERY_ENABLED")):
        raise RuntimeError("owner_test_delivery_switches_must_be_disabled")
    if (env.get("GITHUB_REF") !=
            "refs/heads/release-rasd-hourly-contract-20261121"
            or env.get("GITHUB_EVENT_NAME") != "push"
            or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or not re.fullmatch(r"\\d{8,15}", env.get("GITHUB_RUN_ID", ""))):
        raise RuntimeError("owner_test_wrong_oneoff_workflow_context")
    sender = env.get("RASD_GMAIL_SENDER", "").strip().lower()
    recipient = env.get("RASD_REPORT_TO", "").strip().lower()
    password = "".join(env.get("RASD_GMAIL_APP_PASSWORD", "").split())
    if (not re.fullmatch(r"[^@\\s]+@gmail\\.com", sender)
            or not re.fullmatch(r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", recipient)
            or sender == recipient
            or len(password) < 12
            or hashlib.sha256(recipient.encode()).hexdigest() != PERSONAL_OWNER_SHA256):
        raise RuntimeError("owner_test_personal_mailbox_identity_hold")
    if (env.get("RASD_REPORT_CC") not in ("", None)
            or env.get("RASD_REPORT_BCC") not in ("", None)
            or env.get("RASD_PRIVATE_LEDGER_TOKEN") not in ("", None)):
        raise RuntimeError("owner_test_no_copy_and_no_private_ledger_required")
    return sender, recipient, password, env["GITHUB_RUN_ID"]


def unique_test_key(run_id: str) -> str:
    if not re.fullmatch(r"\\d{8,15}", run_id):
        raise ValueError("owner_test_run_id_invalid")
    return hashlib.sha256(("rasd-owner-only-isolated-test-20261123:"
                           + run_id).encode()).hexdigest()[:24]


def assert_not_previously_sent(sender: str, password: str, test_key: str) -> None:
    """Fail closed if sender Sent cannot be inspected, or the exact key exists."""
    client = imaplib.IMAP4_SSL(
        "imap.gmail.com", 993, ssl_context=ssl.create_default_context(),
        timeout=25)
    try:
        status, _ = client.login(sender, password)
        if status != "OK":
            raise RuntimeError("owner_test_sender_imap_login_hold")
        sent_mailbox(client)
        message_id = f"<rasd-{test_key}@gmail.com>"
        status, rows = client.uid(
            "SEARCH", None, "HEADER", "Message-ID", '"' + message_id + '"')
        if status != "OK" or not rows:
            raise RuntimeError("owner_test_sent_search_unavailable_hold")
        if rows[0]:
            raise RuntimeError("owner_test_already_sent_never_retry")
    except (imaplib.IMAP4.error, OSError, TimeoutError):
        raise RuntimeError("owner_test_sender_imap_unavailable_hold") from None
    finally:
        try:
            client.logout()
        except Exception:
            pass


def build_real_hour_word(folder: Path) -> tuple[Path, int, int, int, str]:
    """Same production original-RSS→capture→Arabic Word rendering; no SMTP."""
    cfg = json.loads(Path("sources_newsroom_active.json").read_text("utf-8"))
    now = datetime.now(timezone.utc)
    start, end = last_completed_hour(now)
    health = []
    candidates = worker.discover_interval_news(
        cfg, now, allow_degraded=True, source_records=health,
        published_before=end,
    )
    audit = audit_fresh_distinct_sources(
        candidates, cfg["feeds"], now, required=10, max_items=10,
    )
    if len(audit["candidate_decisions"]) != len(candidates):
        raise RuntimeError("owner_test_candidate_audit_incomplete_hold")
    # Original photos are verified AFTER fresh-hour selection; an older
    # recovery item cannot masquerade as a new article of this hour.
    picked = audit["selected"]
    held = []
    word = None
    selected = []
    if picked:
        try:
            word, selected, _, _ = worker.prepare_source_limited_verified_word(
                picked, cfg, folder,
                title="رصد | تقرير المتابعة الساعية — تجربة شخصية فقط",
                start=cairo_display_time(start),
                end=cairo_display_time(end),
                source_records=health, held_items=held,
                report_kind="hourly",
            )
        except RuntimeError as error:
            if str(error) != "no_original_publisher_page_verified":
                raise
    if not selected:
        # Use the exact production ZERO/IMAGE-HOLD Word path but replace
        # both real ledger and real SMTP with local offline mocks.
        ledger = MagicMock()
        ledger.reserve.return_value = "reserved"
        start_clock, _, slot = hourly_period(now)
        with patch.object(worker, "send_one_word",
                          return_value="<offline-staging-not-an-email@gmail.com>") as mock:
            worker.send_empty_interval_status(
                ledger=ledger, sender="only-mock@gmail.com",
                recipient="only-mock@example.org", password="not-used",
                state={"entries": {}}, config=cfg, health=health,
                window=slot, start=start_clock, now=now, output=folder,
                hourly=True, fresh_candidates=len(picked),
                held_articles=len(held), original_image_verified=0,
            )
            word = mock.call_args.args[0]
        if not word or not word.is_file():
            raise RuntimeError("owner_test_zero_word_missing_hold")
    document = Document(word)
    links = {rel.target_ref for rel in document.part.rels.values()
             if rel.reltype.endswith("/hyperlink")}
    if len(document.inline_shapes) != len(selected):
        raise RuntimeError("owner_test_embedded_original_count_hold")
    if selected:
        if any(row["url"] not in links for row in selected):
            raise RuntimeError("owner_test_original_links_not_in_word_hold")
        proofs = []
        for row in selected:
            if row.get("hourly_publication_bucket") != "within_previous_hour":
                raise RuntimeError("owner_test_old_story_in_fresh_hour_hold")
            image = Path(row["evidence_image_path"])
            proofs.append({"status": "verified",
                           "sha256": hashlib.sha256(image.read_bytes()).hexdigest()})
        if not word_images_match_capture_digests(word, proofs):
            raise RuntimeError("owner_test_word_photo_sha256_mismatch_hold")
    if not 3000 <= word.stat().st_size <= 8_000_000:
        raise RuntimeError("owner_test_word_attachment_size_hold")
    return (word, len(selected), len(held),
            len([s for s in health if s.get("status") == "failed"]),
            start.astimezone(CAIRO).strftime("%Y-%m-%d %H:00"))


def send_personal_test():
    sender, recipient, password, run_id = require_isolated_scope(os.environ)
    # Env hard stop: production CC/BCC are never inherited, including
    # if someone accidentally adds variables to the protected environment.
    os.environ["RASD_REPORT_CC"] = ""
    os.environ["RASD_REPORT_BCC"] = ""
    key = unique_test_key(run_id)
    assert_not_previously_sent(sender, password, key)
    with tempfile.TemporaryDirectory(prefix="rasd-owner-only-") as folder:
        target = Path(folder)
        word, count, photo_hold, failed_feeds, hour_label = (
            build_real_hour_word(target))
        subject = (f"رصد | تجربة شخصية معزولة — ليست للوزارة | "
                   f"ساعة {hour_label} القاهرة | اختبار {run_id}")
        # This private, ephemeral test ledger never touches production CAS.
        # Attempt=1, exact Message-ID Sent precheck and no automatic retries.
        local_receipt = target / "owner-isolated-test-ledger.json"
        local_receipt.write_text(json.dumps({
            "test": True, "status": "reserved", "key": key,
            "word_digest": hashlib.sha256(word.read_bytes()).hexdigest(),
        }), encoding="utf-8")
        smtp_class = worker.smtplib.SMTP_SSL
        class OwnerOnlySMTP:
            def __init__(self, *args, **kwargs):
                self._smtp = smtp_class(*args, **kwargs)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return self._smtp.__exit__(*args)
            def login(self, *args, **kwargs):
                return self._smtp.login(*args, **kwargs)
            def send_message(self, msg, *, from_addr, to_addrs):
                if (from_addr != sender or to_addrs != [recipient]
                        or msg.get("To") != recipient
                        or msg.get("Cc") is not None
                        or msg.get("Bcc") is not None
                        or msg.get("Message-ID") != f"<rasd-{key}@gmail.com>"):
                    raise RuntimeError("owner_test_envelope_not_personal_only_hold")
                print("RASD_OWNER_ONLY_ENVELOPE_PREFLIGHT=PASS_CCBCC_ZERO",
                      flush=True)
                return self._smtp.send_message(
                    msg, from_addr=from_addr, to_addrs=to_addrs)
        with patch.object(worker.smtplib, "SMTP_SSL", OwnerOnlySMTP):
            receipt = worker.send_one_word(
                word, sender=sender, recipient=recipient, password=password,
                subject=subject, key=key,
                body_text=(
                    "تجربة تسليم شخصية معزولة لمالك رصد فقط، ليست للوزارة. "
                    "الملف يعرض حصيلة ساعة القاهرة المكتملة فعلًا، "
                    "ولا يحتوي أخبارًا أقدم لاستكمال العدد المستهدف. "
                    "تُراجع أدلة الصور وعناوين الناشرين قبل اعتبار أي تغطية موثقة."
                ))
        if receipt != f"<rasd-{key}@gmail.com>":
            raise RuntimeError("owner_test_smtp_receipt_identity_hold")
        local_receipt.write_text(json.dumps({
            "test": True, "status": "smtp_accepted",
            "key": key,
            "word_digest": hashlib.sha256(word.read_bytes()).hexdigest(),
        }), encoding="utf-8")
        print("RASD_OWNER_PERSONAL_ISOLATED_SMTP=" + json.dumps({
            "status": "accepted_unconfirmed_inbox",
            "run_id": run_id,
            "hour_cairo": hour_label,
            "articles": count,
            "images": count,
            "publisher_photo_holds": photo_hold,
            "source_failures": failed_feeds,
            "cc": 0, "bcc": 0, "recipients": 1,
            "private_production_ledger_mutated": False,
            "test_ledger_separate": True,
            "word_bytes": word.stat().st_size,
        }, sort_keys=True), flush=True)


if __name__ == "__main__":
    send_personal_test()
