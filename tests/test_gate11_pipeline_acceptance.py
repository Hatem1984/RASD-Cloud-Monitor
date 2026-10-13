"""Full Gate 11 offline pipeline acceptance: publisher RSS -> capture -> private GitHub CAS -> fake Gmail.

No live network, Gmail messages, real tokens, files on operator's PC,
cron, or billing changes. Mock publisher articles are NEVER live discoveries.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from delivery_bridge import PrivateGitHubLedger, deliver_reserved
from gate11_runner import run
from monitor import article_id

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
PUBLISHED = "Tue, 13 Oct 2026 11:00:00 +0000"
SENDER = "sender@gmail.com"
HAPI = "https://hapijournal.com/gate11-mocked-planning-news"
MASRY = "https://www.almasryalyoum.com/news/details/4380989"
TITLE_HAPI = "وزارة التخطيط تناقش الخطة الاستثمارية"
TITLE_MASRY = "وزارة التخطيط تستعرض مشروعات التنمية"
TEST_JPEG = b"\xff\xd8" + b"J" * 9000
VALID_ENV = {
    "RASD_GATE11_SEND_APPROVED": "YES_I_APPROVE_GMAIL_DELIVERY",
    "RASD_GATE11_RUN_CONFIRMATION": "CONFIRM_ONE_MANUAL_RASD_GMAIL_RUN",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
    "GITHUB_ACTOR": "Hatem1984",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_RUN_ID": "1234512345",
    "RASD_GMAIL_USER": SENDER,
    "RASD_APPROVED_RECIPIENT": SENDER,
    "RASD_GMAIL_APP_PASSWORD": "fake-test-only-value",
    "RASD_PRIVATE_LEDGER_TOKEN": "mock_only_fake_credential_12345",
}


def rss(items):
    body = "".join(
        f"<item><title>{title}</title><link>{url}</link>"
        f"<pubDate>{published}</pubDate></item>"
        for title, url, published in items
    )
    return ("<rss><channel>" + body + "</channel></rss>").encode()


class FakeGithubContents:
    def __init__(self):
        self.state = {
            "schema_version": 2,
            "approved_recipient_sha256": hashlib.sha256(SENDER.encode()).hexdigest(),
            "entries": {},
        }
        self.sha = "initial-state-sha"
        self.writes = 0
        self.spoof_second_write = False

    def open(self, request, timeout):
        assert timeout == 20
        assert request.get_header("Authorization", "").startswith("Bearer ")
        assert "/repos/Hatem1984/RASD-Pilot/contents/delivery-state.json" in request.full_url
        if request.get_method() == "GET":
            assert request.full_url.endswith("?ref=rasd-private-delivery-state")
            value = {
                "sha": self.sha,
                "encoding": "base64",
                "content": base64.b64encode(json.dumps(self.state).encode()).decode(),
            }
            return io.BytesIO(json.dumps(value).encode())
        assert request.get_method() == "PUT"
        item = json.loads(request.data.decode())
        assert item["branch"] == "rasd-private-delivery-state"
        assert item["sha"] == self.sha
        if self.spoof_second_write and self.writes == 1:
            # Simulate an HTTP-success-like GitHub response which never persists.
            return io.BytesIO(b'{"commit":{"sha":"unpersisted-commit"}}')
        self.state = json.loads(base64.b64decode(item["content"]))
        self.sha = hashlib.sha256(item["content"].encode()).hexdigest()
        self.writes += 1
        return io.BytesIO(json.dumps({"commit": {"sha": self.sha}}).encode())


class FakeGmailSMTP:
    transmissions = []
    def __init__(self, host, port, timeout, context):
        assert host == "smtp.gmail.com" and port == 465 and timeout == 25
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def login(self, user, password):
        assert user == SENDER and password == VALID_ENV["RASD_GMAIL_APP_PASSWORD"]
    def send_message(self, message, from_addr, to_addrs):
        assert from_addr == SENDER and to_addrs == [SENDER]
        assert message["From"] == message["To"] == SENDER
        assert message.get_all("Bcc") is None
        assert message.get_all("Cc") is None
        parts = list(message.iter_attachments())
        assert len(parts) == 1 and parts[0].get_content_type() == "image/jpeg"
        assert parts[0].get_payload(decode=True) == TEST_JPEG
        self.transmissions.append((message["X-RASD-Article-ID"], message["Message-ID"]))
        return {}


class FullPipelineAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.private_api = FakeGithubContents()
        FakeGmailSMTP.transmissions = []
        self.captures = []
        self.env = dict(VALID_ENV)

    def fake_fetch(self, url, limit):
        if url == "https://hapijournal.com/feed/":
            return rss([(TITLE_HAPI, HAPI, PUBLISHED)])
        if url == "https://www.almasryalyoum.com/rss/rssfeeds":
            return rss([(TITLE_MASRY, MASRY, PUBLISHED)])
        raise AssertionError("unreviewed feed read")

    def capture(self, url, publisher, destination):
        self.captures.append((url, publisher))
        if url not in (HAPI, MASRY):
            raise AssertionError("unapproved article screenshot")
        destination.write_bytes(TEST_JPEG)
        return {"ok": True, "actual_url": url,
                "title": TITLE_HAPI if url == HAPI else TITLE_MASRY}

    @staticmethod
    def deliver_with_fake_smtp(article, image, **kwargs):
        return deliver_reserved(article, image, **kwargs,
                                smtp_factory=FakeGmailSMTP)

    def execute(self, *, fetch=None, capture=None, deliver=None, mode="send"):
        with patch.dict(os.environ, self.env, clear=True), patch(
                "delivery_bridge.build_opener", return_value=self.private_api):
            return run(mode, fetch=fetch or self.fake_fetch,
                       capture=capture or self.capture,
                       ledger_factory=PrivateGitHubLedger,
                       deliver=deliver or self.deliver_with_fake_smtp,
                       clock=NOW)

    def test_two_native_publishers_two_receipts_second_run_no_duplicate(self):
        first = self.execute()
        self.assertEqual(first["healthy_sources"], 2)
        self.assertEqual(first["planning_headline_matches"], 2)
        self.assertEqual(first["eligible"], 2)
        self.assertEqual(first["captured"], 2)
        self.assertEqual(first["smtp_accepted"], 2)
        self.assertEqual(first["scheduler_enabled"], False)
        self.assertEqual(self.private_api.writes, 4)
        self.assertEqual(len(FakeGmailSMTP.transmissions), 2)
        self.assertEqual({article_id(HAPI), article_id(MASRY)},
                         set(self.private_api.state["entries"]))
        for item in self.private_api.state["entries"].values():
            self.assertEqual(item["status"], "smtp_accepted")
        again = self.execute()
        self.assertEqual(again["already_accepted"], 2)
        self.assertEqual(again["smtp_accepted"], 0)
        self.assertEqual(self.private_api.writes, 4)
        self.assertEqual(len(FakeGmailSMTP.transmissions), 2)

    def test_mismatched_page_title_prevents_reservation_and_sending(self):
        def wrong_capture(url, publisher, destination):
            ret = self.capture(url, publisher, destination)
            ret["title"] = "خبر آخر من ناشر مختلف"
            return ret
        report = self.execute(capture=wrong_capture)
        self.assertEqual(report["rejected_capture"], 2)
        self.assertEqual(report["smtp_accepted"], 0)
        self.assertEqual(self.private_api.writes, 0)
        self.assertEqual(FakeGmailSMTP.transmissions, [])

    def test_historical_news_stays_excluded_even_when_source_is_available(self):
        def old_feed(url, limit):
            if "hapi" in url:
                return rss([(TITLE_HAPI, HAPI, "Mon, 01 Jan 2024 11:00:00 +0000")])
            return rss([(TITLE_MASRY, MASRY, "Mon, 01 Jan 2024 11:00:00 +0000")])
        report = self.execute(fetch=old_feed)
        self.assertEqual(report["eligible"], 0)
        self.assertEqual(report["captured"], 0)
        self.assertEqual(self.private_api.writes, 0)
        self.assertEqual(FakeGmailSMTP.transmissions, [])

    def test_after_smtp_accepted_lost_private_receipt_stays_on_hold(self):
        self.private_api.spoof_second_write = True
        def one_feed(url, limit):
            if "hapi" in url:
                return rss([(TITLE_HAPI, HAPI, PUBLISHED)])
            return rss([])
        with self.assertRaisesRegex(RuntimeError, "private_ledger_commit_not_visible"):
            self.execute(fetch=one_feed)
        self.assertEqual(len(FakeGmailSMTP.transmissions), 1)
        self.assertEqual(self.private_api.state["entries"][article_id(HAPI)]["status"], "reserved")
        again = self.execute(fetch=one_feed)
        self.assertEqual(again["manual_review_hold"], 1)
        self.assertEqual(again["smtp_accepted"], 0)
        self.assertEqual(len(FakeGmailSMTP.transmissions), 1)

    def test_one_publisher_outage_keeps_valid_other_one_with_degraded_status(self):
        def broken_hapi(url, limit):
            if "hapi" in url:
                raise TimeoutError("simulated public source outage")
            return rss([(TITLE_MASRY, MASRY, PUBLISHED)])
        report = self.execute(fetch=broken_hapi)
        self.assertEqual(report["coverage_status"], "degraded")
        self.assertEqual(report["healthy_sources"], 1)
        self.assertEqual(report["failed_sources"], 1)
        self.assertEqual(report["smtp_accepted"], 1)
        self.assertEqual(FakeGmailSMTP.transmissions[0][0], article_id(MASRY))
        self.assertEqual(self.private_api.writes, 2)

    def test_wrong_git_actor_fails_before_reading_feed_or_ledger(self):
        self.env["GITHUB_ACTOR"] = "unapproved-user"
        def must_not_fetch(*args):
            raise AssertionError("must not reach public network before auth")
        with self.assertRaisesRegex(RuntimeError, "gmail_delivery_requires_approved_repo_owner"):
            self.execute(fetch=must_not_fetch)
        self.assertEqual(self.private_api.writes, 0)
        self.assertEqual(FakeGmailSMTP.transmissions, [])

    def test_dry_run_uses_no_private_ledger_and_no_email_even_with_valid_secrets(self):
        def no_delivery(*args, **kwargs):
            raise AssertionError("dry run cannot access Gmail")
        report = self.execute(mode="dry_run", deliver=no_delivery)
        self.assertEqual(report["captured"], 2)
        self.assertEqual(report["smtp_accepted"], 0)
        self.assertEqual(self.private_api.writes, 0)
        self.assertEqual(FakeGmailSMTP.transmissions, [])


if __name__ == "__main__":
    unittest.main()
