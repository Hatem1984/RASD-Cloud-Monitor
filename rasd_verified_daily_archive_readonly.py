"""Read-only trust bridge from existing RASD web Sent archive to daily REVIEW.

Requires actual private CAS + Gmail Sent original attachments. Never calls
SMTP, private CAS PUT, send functions, or production scheduler. Social has NO
accepted archive/schema yet and therefore stays HOLD, not fabricated.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import imaplib
import json
import os
import re
import ssl
import tempfile
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from daily_sent_consolidator import (
    original_sent_word, sent_mailbox, extract_sent_originals)
from daily_report import CAIRO
from delivery_bridge import PrivateGitHubLedger, validate_ledger
from rasd_four_reports_review import (
    build_four_reports, daily_window, render_word, validate_item, CHANNELS)
from scheduled_rasd import news_for_rollup, approved_report_copy

MAX_ACCEPTED_WEB = 60
_MSG_ID = re.compile(r"<rasd-[0-9a-f]{24}@gmail\.com>\Z")


def _accepted_groups(private_state: dict, day: date, config: dict) -> list[tuple[str, list[dict]]]:
    """Reuse current production accepted-entry semantics, preserve mail order."""
    validate_ledger(private_state)
    eligible = news_for_rollup(private_state, day.isoformat(), config)
    if len(eligible) > MAX_ACCEPTED_WEB:
        raise RuntimeError("archive_web_day_too_large_hold")
    wanted = {item["id"]: item for item in eligible}
    accepted = defaultdict(list)
    for key, row in private_state["entries"].items():
        if key not in wanted:
            continue
        if (row.get("kind") != "interval_item"
                or row.get("status") != "smtp_accepted"
                or row.get("news") != wanted[key]
                or not _MSG_ID.fullmatch(str(row.get("message_id", "")))):
            raise RuntimeError("archive_web_ledger_identity_hold")
        accepted[row["message_id"]].append(row["news"])
    if sum(len(group) for group in accepted.values()) != len(eligible):
        raise RuntimeError("archive_web_missing_accepted_rows_hold")
    if any(len(group) > 15 for group in accepted.values()):
        raise RuntimeError("archive_mail_items_exceed_batch_hold")
    return list(accepted.items())


def _source_date(row: dict) -> datetime:
    raw = row.get("published_at_cairo")
    if not isinstance(raw, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} (?:EET|EEST)", raw):
        raise RuntimeError("archive_publisher_time_hold")
    try:
        local = datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
        cairo = local.replace(tzinfo=CAIRO)
        # The fall-back hour can occur twice; do not guess.
        if (cairo.replace(fold=1).utcoffset() != cairo.utcoffset()
                or cairo.tzname() != raw.rsplit(" ", 1)[-1]):
            raise ValueError
        return cairo.astimezone(timezone.utc)
    except ValueError:
        raise RuntimeError("archive_publisher_time_hold") from None


def accepted_web_daily_review(
    *, day: date, now: datetime, output: Path,
    sender: str, recipient: str, app_password: str,
    ledger_token: str, client_factory=None,
    ledger_factory=PrivateGitHubLedger, approved_copy: str | None = None,
    message_reader=original_sent_word, extractor=extract_sent_originals,
) -> dict:
    """CAS GET + Gmail Sent readonly IMAP + original Word image bindings."""
    if (now.tzinfo is None or now.utcoffset() is None
            or not re.fullmatch(r"[^@\s]+@gmail\.com", sender or "", re.I)
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recipient or "")
            or sender.casefold() == recipient.casefold()
            or len(app_password or "") < 12 or len(ledger_token or "") < 16):
        raise RuntimeError("readonly_archive_credentials_hold")
    if now.astimezone(timezone.utc) < daily_window(day)[1]:
        raise RuntimeError("daily_archive_window_in_future_hold")
    config = json.loads(
        Path(__file__).with_name("sources_newsroom_active.json")
        .read_text(encoding="utf-8"))
    ledger = ledger_factory(ledger_token)
    state, _sha = ledger.read()  # Reads only; never reserve or write.
    validate_ledger(state)
    digest = hashlib.sha256(recipient.casefold().encode("utf-8")).hexdigest()
    if not hmac.compare_digest(
            digest, state["approved_recipient_sha256"]):
        raise RuntimeError("readonly_archive_recipient_not_approved")
    accepted = _accepted_groups(state, day, config)
    # Fail closed if one of the original sent attachments is unavailable.
    prepared = []
    allowed_hosts = {host for f in config["feeds"]
                     for host in f["allowed_article_hosts"]}
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
            prefix="rasd-originals-readonly-", dir=output) as tmp:
        temp = Path(tmp)
        if accepted:
            client = client_factory() if client_factory else imaplib.IMAP4_SSL(
                "imap.gmail.com", 993, ssl_context=ssl.create_default_context(),
                timeout=25)
            try:
                status, _ = client.login(sender, app_password)
                if status != "OK":
                    raise RuntimeError("archive_imap_login_hold")
                sent_mailbox(client)  # SELECT readonly=True
                for msgid, group in accepted:
                    original = message_reader(
                        client, msgid, sender, recipient,
                        approved_copy=approved_copy)
                    proof = extractor(original, group, temp)
                    if (len(proof) != len(group)
                            or [x["id"] for x in group] !=
                               [item["id"] for item, _, _ in proof]):
                        raise RuntimeError("archive_original_order_hold")
                    for article, image_path, image_sha in proof:
                        published = _source_date(article)
                        url = article["url"]
                        canonical = hashlib.sha256(
                            ("web:" + url).encode("utf-8")).hexdigest()
                        prepared.append({
                            "channel": "web", "platform": None,
                            "source": article["source"],
                            "title": article["headline"], "url": url,
                            "published_at": published.isoformat(),
                            "id": canonical, "image_path": image_path,
                            "image_sha256": image_sha,
                            "capture_receipt": {
                                "status": "verified", "url": url,
                                "sha256": image_sha,
                                "method": "approved_web_publisher_capture"},
                            "accepted_at": state["entries"][article["id"]]["accepted_at"],
                            "message_id": msgid,
                        })
            finally:
                try:
                    client.logout()
                except Exception:
                    pass
        validated = [
            validate_item(row, "web", temp, allowed_hosts,
                          cutoff=now.astimezone(timezone.utc))
            for row in prepared]
        start, end = daily_window(day)
        if any(not start <= datetime.fromisoformat(
                row["accepted_at"]).astimezone(timezone.utc) < end
               for row in validated):
            raise RuntimeError("archive_delivery_time_outside_day_hold")
        # Preserve existing source/Meta HOLD in independent four-output layout.
        states = [
            {"channel": "web",
             "name": "توافر المصادر التاريخي: لم يُستخرج من سجل Sent",
             "status": "hold"},
            *[{"channel": "social", "name": p, "status": "unauthorized"}
              for p in ("Facebook", "X", "Instagram", "LinkedIn")],
        ]
        base = build_four_reports(
            [], states, [], cutoff=now, date_cairo=day,
            evidence_root=temp, output=output,
            allowed_web_hosts=allowed_hosts)
        saved = render_word(
            "web", "daily", validated, [states[0]], start, end,
            output / "RASD-Web-Daily-REVIEW-NOT-SENT.docx")
        base["reports"]["web-daily"] = saved
        base["archive_status"] = (
            "CAS_AND_READONLY_GMAIL_ORIGINALS_VERIFIED" if accepted
            else "CAS_READ_NO_ACCEPTED_EMAILS_NO_IMAP_NEEDED")
        base["read_only_verified_web_daily_items"] = len(validated)
        base["social_daily_status"] = "HOLD_NO_SOCIAL_ACCEPTED_PRODUCTION_LEDGER"
        base["smtp_sent"] = False
        base["daily_receipts_proven_by_this_builder"] = False
        base["note"] = ("Web daily image/receipt verification used CAS GET and "
                        "readonly Gmail Sent originals. No authorized social "
                        "delivery ledger is configured; other outputs remain HOLD.")
        (output / "RASD-Four-Reports-REVIEW-MANIFEST.json").write_text(
            json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
        return base


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RASD old accepted web daily trust review, NEVER SEND")
    parser.add_argument("--read-accepted-web", action="store_true",
                        help="Opt in to PRIVATE CAS GET and Gmail Sent IMAP read-only")
    parser.add_argument("--day", required=True, help="YYYY-MM-DD Cairo 22h cutoff")
    parser.add_argument("--out", type=Path,
                        default=Path("report-output/verified-archive-daily"))
    args = parser.parse_args()
    if not args.read_accepted_web:
        print(json.dumps({"status": "HOLD_EXPLICIT_READONLY_OPT_IN_REQUIRED",
                          "smtp_sent": False}))
        return
    protected_output_root = (
        Path(__file__).resolve().parent / "report-output").resolve()
    if not args.out.resolve().is_relative_to(protected_output_root):
        print(json.dumps({"status": "HOLD_OUTPUT_MUST_REMAIN_LOCAL_IGNORED",
                          "smtp_sent": False}))
        raise SystemExit(1)
    try:
        result = accepted_web_daily_review(
            day=date.fromisoformat(args.day), now=datetime.now(timezone.utc),
            output=args.out,
            sender=os.environ.get("RASD_GMAIL_SENDER", ""),
            recipient=os.environ.get("RASD_REPORT_TO", ""),
            app_password="".join(
                os.environ.get("RASD_GMAIL_APP_PASSWORD", "").split()),
            ledger_token=os.environ.get("RASD_PRIVATE_LEDGER_TOKEN", ""),
            approved_copy=approved_report_copy(
                os.environ.get("RASD_GMAIL_SENDER", ""),
                os.environ.get("RASD_REPORT_TO", "")),
        )
    except (ValueError, RuntimeError, OSError, imaplib.IMAP4.error):
        print(json.dumps({"status": "HOLD_PRIVATE_ARCHIVE_VERIFICATION",
                          "smtp_sent": False, "ledger_mutated": False}))
        raise SystemExit(1) from None
    print(json.dumps({"status": result["archive_status"],
                      "web_daily_items": result["read_only_verified_web_daily_items"],
                      "smtp_sent": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
