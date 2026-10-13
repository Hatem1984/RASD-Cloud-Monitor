"""Gate 13 integration tests: fake publisher RSS + real DOCX/PDF parser + mock private GitHub + fake SMTP.

The tests never authenticate Gmail or write to a real private repository.
"""
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter

from digest_mailer import (
    WORKFLOW_REF, build_digest_message, deliver_digest, report_identity, run,
)
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


def pdf_builder(report, path):
    writer = PdfWriter()
    for _ in range(25):
        writer.add_blank_page(width=595, height=842)
    with path.open("wb") as handle:
        writer.write(handle)


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
        assert len(parts) == 2, "Exactly Word and PDF"
        assert parts[0].get_content_type() == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert parts[1].get_content_type() == "application/pdf"
        assert parts[0].get_payload(decode=True).startswith(b"PK")
        assert parts[1].get_payload(decode=True).startswith(b"%PDF-")
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

    def execute(self, *, pdf=pdf_builder, fetch=None):
        with patch.dict(os.environ, self.env, clear=True), \
             patch("delivery_bridge.build_opener", return_value=self.api), \
             patch("daily_report.render_pdf", side_effect=pdf):
            return run(clock=CLOCK, fetch=fetch or self.fetch,
                       smtp_factory=FakeSMTPSender)

    def test_digest_real_document_files_two_attachments_and_one_private_receipt(self):
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
        second = self.execute()
        self.assertEqual(second["status"], "already_accepted")
        self.assertEqual(len(FakeSMTPSender.sent), 1)
        self.assertEqual(self.api.writes, 2)

    def test_no_history_or_match_still_reports_actual_zero_rss_headlines(self):
        outcome = self.execute(fetch=lambda url, limit: rss())
        self.assertEqual(outcome["articles"], 0)
        self.assertTrue(outcome["smtp_accepted"])
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

    def test_bad_pdf_never_reserves_or_sends(self):
        def invalid_pdf(report, file):
            file.write_bytes(b"not PDF content" * 400)
        with self.assertRaisesRegex(ValueError, "report_attachment_format_invalid"):
            self.execute(pdf=invalid_pdf)
        self.assertEqual(self.api.writes, 0)
        self.assertEqual(len(FakeSMTPSender.sent), 0)

    def test_after_smtp_receipt_write_failure_next_run_stays_on_hold(self):
        self.api.spoof_second_write = True
        with self.assertRaisesRegex(RuntimeError, "private_ledger_commit_not_visible"):
            self.execute()
        self.assertEqual(len(FakeSMTPSender.sent), 1)
        key = report_identity(CLOCK)[1]
        self.assertEqual(self.api.state["entries"][key]["status"], "reserved")
        self.assertEqual(self.execute()["status"], "manual_review_hold")
        self.assertEqual(len(FakeSMTPSender.sent), 1)

    def test_one_feed_outage_reports_degraded_but_all_down_fails_before_reservation(self):
        def partial(url, limit):
            if "hapijournal" in url:
                raise TimeoutError("simulate partial outage")
            return rss()
        result = self.execute(fetch=partial)
        self.assertEqual(result["coverage"], "DEGRADED")
        self.assertEqual(result["articles"], 0)
        self.assertTrue(result["smtp_accepted"])
        self.api = FakeGithubContents()
        FakeSMTPSender.sent = []
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
