"""Gate 13 integration tests: fake publisher RSS + real Word image parser + mock private GitHub + fake SMTP.

The tests never authenticate Gmail or write to a real private repository.
"""
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from digest_mailer import (
    WORKFLOW_REF, build_digest_message, deliver_digest, report_identity, run,
)
from cloud_proof_report import build_proof_report
from test_gate11_pipeline_acceptance import FakeGithubContents

CLOCK = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
SENDER = "sender@gmail.com"
ENV = {
    "RASD_GATE11_SEND_APPROVED": "YES_I_APPROVE_GMAIL_DELIVERY",
    "RASD_GATE11_RUN_CONFIRMATION": "CONFIRM_ONE_MANUAL_RASD_GMAIL_RUN",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
    "GITHUB_ACTOR": "Hatem1984",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_RUN_ID": "99887766",
    "GITHUB_WORKFLOW_REF": WORKFLOW_REF,
    "RASD_GMAIL_USER": SENDER,
    "RASD_APPROVED_RECIPIENT": SENDER,
    "RASD_GMAIL_APP_PASSWORD": "fake-test-only-value",
    "RASD_PRIVATE_LEDGER_TOKEN": "mock_only_private_api_credential",
}


def rss(title=None, url=None, date="Tue, 13 Oct 2026 10:00:00 GMT"):
    if not title:
        return b"<rss><channel></channel></rss>"
    return (f"<rss><channel><item><title>{title}</title><link>{url}</link>"
            f"<pubDate>{date}</pubDate></item></channel></rss>").encode("utf-8")


def publisher_fetch(url, limit):
    if "hapijournal" in url:
        return rss("وزارة التخطيط تراجع مؤشرات التنمية",
                   "https://hapijournal.com/test-digest-original-article")
    if "almasryalyoum" in url:
        return rss()
    raise AssertionError("unapproved RSS URL")


def publisher_capture(url, publisher, destination):
    image = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1199, 200), fill=(13, 32, 55))
    for y in range(220, 870, 30):
        draw.rectangle((35, y, 1150, y + 16), fill=(30, 44, 60))
    image.save(destination, quality=90)
    return {"ok": True, "actual_url": url,
            "title": "وزارة التخطيط تراجع مؤشرات التنمية"}


class FakeSMTPSender:
    sent = []
    def __init__(self, hostname, port, timeout, context):
        assert hostname == "smtp.gmail.com" and port == 465 and timeout == 25
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def login(self, address, password):
        assert address == SENDER and password == ENV["RASD_GMAIL_APP_PASSWORD"]
    def send_message(self, msg, from_addr, to_addrs):
        assert from_addr == SENDER and to_addrs == [SENDER]
        assert msg["From"] == SENDER and msg["To"] == SENDER
        assert not msg.get_all("Bcc") and not msg.get_all("Cc")
        parts = list(msg.iter_attachments())
        assert len(parts) == 1, "Exactly one Word attachment"
        assert parts[0].get_content_type() == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert parts[0].get_payload(decode=True).startswith(b"PK")
        assert parts[0].get_filename().endswith(".docx")
        self.sent.append(msg)
        return {}


class DailyProtectedEmailTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeGithubContents()
        self.env = dict(ENV)
        FakeSMTPSender.sent = []
        self.feed_calls = []

    def fetch(self, url, limit):
        self.feed_calls.append(url)
        return publisher_fetch(url, limit)

    def execute(self, *, capture=publisher_capture, fetch=None):
        with patch.dict(os.environ, self.env, clear=True), \
             patch("delivery_bridge.build_opener", return_value=self.api):
            return run(clock=CLOCK, fetch=fetch or self.fetch, capture=capture,
                       smtp_factory=FakeSMTPSender)

    def test_digest_one_verified_word_attachment_and_one_private_receipt(self):
        first = self.execute()
        self.assertEqual(first["date_cairo"], "2026-10-13")
        self.assertEqual(first["articles"], 1)
        self.assertTrue(first["smtp_accepted"])
        self.assertFalse(first["inbox_delivery_verified"])
        self.assertFalse(first["scheduler_enabled"])
        self.assertEqual(len(FakeSMTPSender.sent), 1)
        self.assertEqual(len(self.feed_calls), 2)
        key = report_identity(CLOCK)[1]
        self.assertEqual(self.api.state["entries"][key]["status"], "smtp_accepted")
        self.assertEqual(self.api.writes, 2)
        def forbidden_rss(*args):
            raise AssertionError("Same-day replay must not scan publishers")
        def forbidden_capture(*args):
            raise AssertionError("Same-day replay must not capture images")
        second = self.execute(capture=forbidden_capture, fetch=forbidden_rss)
        self.assertEqual(second["status"], "already_accepted")
        self.assertTrue(second["source_scan_skipped"])
        self.assertIsNone(second["articles"])
        self.assertEqual(second["coverage"], "NOT_RESCANNED")
        self.assertEqual(len(self.feed_calls), 2)
        self.assertEqual(len(FakeSMTPSender.sent), 1)
        self.assertEqual(self.api.writes, 2)

    def test_changed_word_jpeg_rejected_before_private_reservation_or_smtp(self):
        """A Word with the expected picture count but tampered JPEG cannot send."""
        class NeverReserve:
            def reserve(self, *args):
                raise AssertionError("invalid evidence must NOT reserve private state")
            def mark_smtp_accepted(self, *args):
                raise AssertionError("invalid evidence must NOT update private state")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            report = build_proof_report(
                Path("sources.json"), folder,
                fetch=publisher_fetch, capture=publisher_capture, now=CLOCK)
            self.assertEqual(report["status"], "READY")
            self.assertEqual(report["articles"], 1)
            date, key = report_identity(CLOCK)
            word = folder / f"RASD-Daily-{date}.docx"
            with zipfile.ZipFile(word) as archive:
                parts = [(part, archive.read(part.filename))
                         for part in archive.infolist()]
            with zipfile.ZipFile(word, "w") as archive:
                for part, raw in parts:
                    if part.filename.startswith("word/media/"):
                        raw += b"modified_after_capture"
                    archive.writestr(part, raw)
            with self.assertRaisesRegex(
                    ValueError, "digest_word_evidence_integrity_failed"):
                deliver_digest(
                    report, date=date, key=key, word=word,
                    sender=SENDER, approved_recipient=SENDER,
                    app_password=ENV["RASD_GMAIL_APP_PASSWORD"],
                    ledger=NeverReserve(), smtp_factory=FakeSMTPSender)
            self.assertEqual(FakeSMTPSender.sent, [])

    def test_missing_independent_capture_receipts_rejected_before_reservation(self):
        class NeverReserve:
            def reserve(self, *args):
                raise AssertionError("unproven Word must NOT reserve private state")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            report = build_proof_report(
                Path("sources.json"), folder,
                fetch=publisher_fetch, capture=publisher_capture, now=CLOCK)
            self.assertEqual(report["status"], "READY")
            report.pop("entries")
            date, key = report_identity(CLOCK)
            with self.assertRaisesRegex(
                    ValueError, "digest_word_evidence_integrity_failed"):
                deliver_digest(
                    report, date=date, key=key,
                    word=folder / f"RASD-Daily-{date}.docx",
                    sender=SENDER, approved_recipient=SENDER,
                    app_password=ENV["RASD_GMAIL_APP_PASSWORD"],
                    ledger=NeverReserve(), smtp_factory=FakeSMTPSender)
            self.assertEqual(FakeSMTPSender.sent, [])

    def test_no_news_holds_instead_of_sending_unverified_word(self):
        with self.assertRaisesRegex(RuntimeError, "digest_publisher_evidence_incomplete"):
            self.execute(fetch=lambda url, limit: rss())
        self.assertEqual(self.api.writes, 0)
        self.assertEqual(len(FakeSMTPSender.sent), 0)

    def test_publisher_access_refused_never_reserves_or_sends(self):
        def blocked(*args):
            return {"ok": False, "reason": "publisher_access_refused"}
        with self.assertRaisesRegex(RuntimeError, "digest_publisher_evidence_incomplete"):
            self.execute(capture=blocked)
        self.assertEqual(self.api.writes, 0)
        self.assertEqual(FakeSMTPSender.sent, [])

    def test_wrong_private_ledger_recipient_fails_before_public_news_scan(self):
        self.api.state["approved_recipient_sha256"] = "0" * 64
        def forbidden_fetch(*args):
            raise AssertionError("wrong private recipient must stop before RSS")
        with self.assertRaisesRegex(RuntimeError, "digest_private_recipient_mismatch"):
            self.execute(fetch=forbidden_fetch)
        self.assertEqual(self.api.writes, 0)
        self.assertEqual(FakeSMTPSender.sent, [])

    def test_replayed_report_can_be_checked_during_total_public_source_outage(self):
        self.execute()
        self.assertEqual(len(FakeSMTPSender.sent), 1)
        def both_sources_down(*args):
            raise TimeoutError("site down: must not get called on replay")
        result = self.execute(fetch=both_sources_down)
        self.assertEqual(result["status"], "already_accepted")
        self.assertTrue(result["source_scan_skipped"])
        self.assertIsNone(result["articles"])
        self.assertEqual(len(FakeSMTPSender.sent), 1)

    def test_missing_consent_prevents_any_source_or_ledger_access(self):
        self.env["RASD_GATE11_RUN_CONFIRMATION"] = ""
        with self.assertRaisesRegex(RuntimeError, "gmail_delivery_requires_per_run_confirmation"):
            self.execute(fetch=lambda *x: self.fail("RSS must not be contacted"))
        self.assertEqual(self.api.writes, 0)
        self.assertFalse(self.feed_calls)

    def test_wrong_workflow_path_never_scans_publishers(self):
        self.env["GITHUB_WORKFLOW_REF"] = (
            "Hatem1984/RASD-Cloud-Monitor/.github/workflows/other.yml@refs/heads/main")
        with self.assertRaisesRegex(RuntimeError, "digest_requires_dedicated_manual_workflow"):
            self.execute(fetch=lambda *x: self.fail("no feed"))
        self.assertEqual(self.api.writes, 0)

    def test_rerun_attempt_cannot_reuse_an_old_approval(self):
        self.env["GITHUB_RUN_ATTEMPT"] = "2"
        with self.assertRaisesRegex(RuntimeError, "gmail_delivery_requires_new_workflow_run"):
            self.execute(fetch=lambda *x: self.fail("no feed"))
        self.assertEqual(FakeSMTPSender.sent, [])

    def test_bad_image_never_reserves_or_sends(self):
        def corrupted_image(url, publisher, path):
            path.write_bytes(b"not-a-screenshot" * 1000)
            return {"ok": True, "actual_url": url,
                    "title": "وزارة التخطيط تراجع مؤشرات التنمية"}
        with self.assertRaisesRegex(RuntimeError, "digest_publisher_evidence_incomplete"):
            self.execute(capture=corrupted_image)
        self.assertEqual(self.api.writes, 0)
        self.assertEqual(FakeSMTPSender.sent, [])

    def test_after_smtp_receipt_write_failure_next_run_stays_on_hold(self):
        self.api.spoof_second_write = True
        with self.assertRaisesRegex(RuntimeError, "private_ledger_commit_not_visible"):
            self.execute()
        self.assertEqual(len(FakeSMTPSender.sent), 1)
        key = report_identity(CLOCK)[1]
        self.assertEqual(self.api.state["entries"][key]["status"], "reserved")
        def forbidden_rss(*args):
            raise AssertionError("HOLD must be read before publishers")
        held = self.execute(fetch=forbidden_rss)
        self.assertEqual(held["status"], "manual_review_hold")
        self.assertTrue(held["source_scan_skipped"])
        self.assertEqual(len(FakeSMTPSender.sent), 1)

    def test_degraded_or_offline_feeds_never_reserve_or_send(self):
        def partial(url, limit):
            if "almasryalyoum" in url:
                raise TimeoutError("simulate partial outage")
            return publisher_fetch(url, limit)
        with self.assertRaisesRegex(RuntimeError, "digest_publisher_evidence_incomplete"):
            self.execute(fetch=partial)
        self.assertEqual(self.api.writes, 0)
        self.assertEqual(FakeSMTPSender.sent, [])
        with self.assertRaisesRegex(RuntimeError, "all_public_RSS_sources_failed"):
            self.execute(fetch=lambda *x: (_ for _ in ()).throw(
                TimeoutError("both feeds down")))
        self.assertEqual(self.api.writes, 0)
        self.assertEqual(FakeSMTPSender.sent, [])

    def test_same_cairo_day_has_same_report_identity_even_at_different_utc_hours(self):
        first = datetime(2026, 10, 12, 22, 30, tzinfo=timezone.utc)
        second = datetime(2026, 10, 13, 18, 20, tzinfo=timezone.utc)
        third = datetime(2026, 10, 13, 22, 30, tzinfo=timezone.utc)
        self.assertEqual(report_identity(first), report_identity(second))
        self.assertNotEqual(report_identity(first), report_identity(third))


if __name__ == "__main__":
    unittest.main()
