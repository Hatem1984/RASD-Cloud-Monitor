"""Gate 11 offline tests: never access Gmail, GitHub network or real credentials."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from delivery_bridge import (
    build_email, complete_entry, deliver_reserved, gmail_submit,
    reserve_entry, validate_ledger,
)
from gate11_runner import candidate_from_feed, eligible_candidates, credentials, run
from monitor import article_id

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
URL = "https://hapijournal.com/example-planning-article"
KEY = article_id(URL)
TITLE = "وزارة التخطيط تعلن خطة اقتصادية جديدة"
ARTICLE = {"id": KEY, "url": URL, "headline": TITLE,
           "published": "Tue, 13 Oct 2026 10:00:00 GMT",
           "source": "Hapi native news RSS"}
CONFIG = {"feeds": [{"id": "hapi", "name": "Hapi native news RSS",
                     "url": "https://hapijournal.com/feed/",
                     "allowed_article_hosts": ["hapijournal.com"]}],
          "keywords": ["وزارة التخطيط"], "recent_hours": 72,
          "max_feed_bytes": 1500000}
JPEG = b"\xff\xd8" + (b"A" * 9000)


class StateMachineTests(unittest.TestCase):
    def test_reserve_then_accept_never_resends(self):
        initial = {"schema_version": 1, "entries": {}}
        reserved, action = reserve_entry(initial, KEY, NOW.isoformat())
        self.assertEqual(action, "reserved")
        self.assertEqual(initial["entries"], {})
        _, action2 = reserve_entry(reserved, KEY, NOW.isoformat())
        self.assertEqual(action2, "manual_review_hold")
        completed = complete_entry(reserved, KEY, NOW.isoformat(),
                                   "<rasd-" + KEY + "@gmail.com>")
        _, action3 = reserve_entry(completed, KEY, NOW.isoformat())
        self.assertEqual(action3, "already_accepted")

    def test_uncertain_state_is_not_automatically_released(self):
        reserved, _ = reserve_entry({"schema_version": 1, "entries": {}},
                                    KEY, NOW.isoformat())
        for i in range(3):
            _, action = reserve_entry(reserved, KEY, NOW.isoformat())
            self.assertEqual(action, "manual_review_hold")

    def test_bad_or_public_style_state_fails_closed(self):
        for state in ({}, {"schema_version": 2, "entries": {}},
                      {"schema_version": 1, "entries": {"test": {}}},
                      {"schema_version": 1, "entries": {},
                       "seen_ids": {KEY: "today"}}):
            with self.assertRaises(ValueError):
                validate_ledger(state)

    def test_cannot_mark_unreserved_as_accepted(self):
        with self.assertRaises(ValueError):
            complete_entry({"schema_version": 1, "entries": {}},
                           KEY, NOW.isoformat(), "<rasd-" + KEY + "@gmail.com>")


class FakeSMTP:
    sent = 0
    recipients = []
    def __init__(self, host, port, timeout, context):
        assert host == "smtp.gmail.com" and port == 465
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def login(self, sender, password):
        assert password == "fake-test-only-value"
    def send_message(self, msg, from_addr, to_addrs):
        self.__class__.sent += 1
        self.__class__.recipients.append(to_addrs)
        return {}


class StubLedger:
    def __init__(self):
        self.state = {"schema_version": 1, "entries": {}}
        self.fail_after_smtp = False
    def reserve(self, key):
        self.state, action = reserve_entry(self.state, key, NOW.isoformat())
        return action
    def mark_smtp_accepted(self, key, message_id):
        if self.fail_after_smtp:
            raise RuntimeError("simulated_receipt_write_failure")
        self.state = complete_entry(self.state, key, NOW.isoformat(), message_id)


class EmailSafetyTests(unittest.TestCase):
    def setUp(self):
        FakeSMTP.sent = 0
        FakeSMTP.recipients = []
        self.email = "sender@gmail.com"
        self.article = {**ARTICLE, "publisher": "hapijournal.com"}

    def test_exactly_one_explicit_recipient(self):
        msg = build_email(self.article, JPEG, self.email)
        self.assertEqual(msg["To"], self.email)
        self.assertEqual(msg["From"], self.email)
        self.assertIsNone(msg["Cc"])
        self.assertIsNone(msg["Bcc"])
        self.assertEqual(len(list(msg.iter_attachments())), 1)
        self.assertIn(URL, msg.get_body(preferencelist=("plain",)).get_content())
        receipt = gmail_submit(msg, self.email, "fake-test-only-value",
                               smtp_factory=FakeSMTP)
        self.assertTrue(receipt.startswith("<rasd-"))
        self.assertEqual(FakeSMTP.recipients, [[self.email]])

    def test_sender_must_match_approved_recipient(self):
        with tempfile.TemporaryDirectory() as p:
            img = Path(p) / "image.jpg"
            img.write_bytes(JPEG)
            with self.assertRaisesRegex(ValueError, "approved_recipient_mismatch"):
                deliver_reserved(self.article, img, sender=self.email,
                                 approved_recipient="someoneelse@gmail.com",
                                 app_password="fake-test-only-value", ledger=StubLedger(),
                                 smtp_factory=FakeSMTP)
            self.assertEqual(FakeSMTP.sent, 0)

    def test_smtp_failure_or_ledger_failure_does_not_resend(self):
        with tempfile.TemporaryDirectory() as p:
            img = Path(p) / "image.jpg"
            img.write_bytes(JPEG)
            ledger = StubLedger()
            ledger.fail_after_smtp = True
            with self.assertRaisesRegex(RuntimeError, "simulated_receipt"):
                deliver_reserved(self.article, img, sender=self.email,
                                 approved_recipient=self.email,
                                 app_password="fake-test-only-value", ledger=ledger,
                                 smtp_factory=FakeSMTP)
            self.assertEqual(FakeSMTP.sent, 1)
            ledger.fail_after_smtp = False
            outcome = deliver_reserved(self.article, img, sender=self.email,
                                       approved_recipient=self.email,
                                       app_password="fake-test-only-value", ledger=ledger,
                                       smtp_factory=FakeSMTP)
            self.assertEqual(outcome, "manual_review_hold")
            self.assertEqual(FakeSMTP.sent, 1)

    def test_reject_other_hosts_untrusted_jpeg_and_header_injection(self):
        with self.assertRaises(ValueError):
            build_email({**self.article, "url": "https://news.google.com/s",
                         "id": article_id("https://news.google.com/s")}, JPEG, self.email)
        with self.assertRaises(ValueError):
            build_email(self.article, b"not-jpeg", self.email)
        with self.assertRaises(ValueError):
            build_email({**self.article, "headline": "bad\r\nBcc: victim@example.com"},
                        JPEG, self.email)

    def test_wrong_recipient_in_mail_is_never_smtp_submitted(self):
        msg = build_email(self.article, JPEG, self.email)
        msg.replace_header("To", "attacker@example.com")
        with self.assertRaisesRegex(ValueError, "recipient_not_the_approved_sender"):
            gmail_submit(msg, self.email, "fake-test-only-value",
                         smtp_factory=FakeSMTP)
        self.assertEqual(FakeSMTP.sent, 0)


class CandidateAndDryRunTests(unittest.TestCase):
    def test_genuine_recent_original_feed_is_eligible(self):
        good = candidate_from_feed(ARTICLE, CONFIG, NOW)
        self.assertEqual(good["publisher"], "hapijournal.com")

    def test_fixture_undated_stale_or_changed_url_is_excluded(self):
        cases = [
            {**ARTICLE, "selection": "historic_publisher_reference_not_new_discovery"},
            {**ARTICLE, "published": None},
            {**ARTICLE, "published": "Tue, 13 Oct 2020 10:00:00 GMT"},
            {**ARTICLE, "id": "0" * 24},
            {**ARTICLE, "url": "https://news.google.com/rss/articles/abc",
             "id": article_id("https://news.google.com/rss/articles/abc")},
            {**ARTICLE, "published": "not-a-date"},
        ]
        for article in cases:
            with self.subTest(article=article):
                self.assertIsNone(candidate_from_feed(article, CONFIG, NOW))

    def test_dry_run_requires_no_credentials_and_does_not_deliver(self):
        xml = ("<rss><channel><item><title>" + TITLE + "</title><link>" +
               URL + "</link><pubDate>Tue, 13 Oct 2026 10:00:00 GMT"
               "</pubDate></item></channel></rss>").encode("utf-8")
        with tempfile.TemporaryDirectory() as p:
            path = Path(p) / "sources.json"
            path.write_text(json.dumps(CONFIG, ensure_ascii=False), encoding="utf-8")
            def mock_capture(url, publisher, dest):
                dest.write_bytes(JPEG)
                return {"ok": True, "actual_url": URL, "title": TITLE}
            def impossible_delivery(*args, **kwargs):
                raise AssertionError("dry-run must never send")
            with patch.dict(os.environ, {}, clear=True):
                result = run("dry_run", config_path=path,
                             fetch=lambda *a: xml, capture=mock_capture,
                             deliver=impossible_delivery, clock=NOW)
            self.assertEqual(result["captured"], 1)
            self.assertEqual(result["smtp_accepted"], 0)
            self.assertFalse(result["scheduler_enabled"])
            self.assertFalse(result["test_fixture_used"])

    def test_send_without_protected_authorization_fails_before_network(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "gmail_delivery_not_authorized"):
                credentials()

    def test_send_authorization_without_all_secrets_fails_closed(self):
        with patch.dict(os.environ, {"RASD_GATE11_SEND_APPROVED":
                                     "YES_I_APPROVE_GMAIL_DELIVERY"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "missing_protected_delivery_configuration"):
                credentials()


if __name__ == "__main__":
    unittest.main()
