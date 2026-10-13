"""Gate 11 offline tests: never access Gmail, GitHub network or real credentials."""
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
from urllib.error import HTTPError

from delivery_bridge import (
    NoGitHubRedirect, PrivateGitHubLedger, build_email, complete_entry, deliver_reserved, gmail_submit,
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

APPROVED_HASH = hashlib.sha256(b"sender@gmail.com").hexdigest()
MANUAL_SEND_ENV = {
    "RASD_GATE11_SEND_APPROVED": "YES_I_APPROVE_GMAIL_DELIVERY",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
    "GITHUB_ACTOR": "Hatem1984",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_RUN_ID": "456789123",
    "RASD_GATE11_RUN_CONFIRMATION": "CONFIRM_ONE_MANUAL_RASD_GMAIL_RUN",
    "RASD_GMAIL_USER": "sender@gmail.com",
    "RASD_APPROVED_RECIPIENT": "sender@gmail.com",
    "RASD_GMAIL_APP_PASSWORD": "fake-test-only-value",
    "RASD_PRIVATE_LEDGER_TOKEN": "mock_token_nonsecret_123456",
}


def empty_private_ledger():
    return {"schema_version": 2, "approved_recipient_sha256": APPROVED_HASH,
            "entries": {}}


class StateMachineTests(unittest.TestCase):
    def test_reserve_then_accept_never_resends(self):
        initial = empty_private_ledger()
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
        reserved, _ = reserve_entry(empty_private_ledger(),
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
            complete_entry(empty_private_ledger(),
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
        self.state = empty_private_ledger()
        self.fail_after_smtp = False
    def reserve(self, key, sender):
        digest = hashlib.sha256(sender.strip().casefold().encode("utf-8")).hexdigest()
        if digest != self.state["approved_recipient_sha256"]:
            raise ValueError("recipient_not_approved_by_private_ledger")
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
        self.article = {**ARTICLE, "publisher": "hapijournal.com",
                        "selection": "live_feed_discovery"}

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

    def test_historical_reference_cannot_reach_email_builder(self):
        with self.assertRaisesRegex(ValueError, "historical_or_undated"):
            build_email({**self.article,
                         "selection": "historic_publisher_reference_not_new_discovery"},
                        JPEG, self.email)
        with self.assertRaisesRegex(ValueError, "historical_or_undated"):
            build_email({**self.article, "published": None}, JPEG, self.email)

    def test_private_ledger_fixes_recipient_despite_matching_env_secrets(self):
        with tempfile.TemporaryDirectory() as p:
            image = Path(p) / "image.jpg"
            image.write_bytes(JPEG)
            ledger = StubLedger()
            with self.assertRaisesRegex(ValueError, "recipient_not_approved_by_private_ledger"):
                deliver_reserved(self.article, image, sender="attacker@gmail.com",
                                 approved_recipient="attacker@gmail.com",
                                 app_password="fake-test-only-value",
                                 ledger=ledger, smtp_factory=FakeSMTP)
            self.assertEqual(FakeSMTP.sent, 0)
            self.assertEqual(ledger.state["entries"], {})

    def test_cross_domain_github_ledger_redirect_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "private_ledger_redirect_forbidden"):
            NoGitHubRedirect().redirect_request(None, None, 302, "Found",
                                                 {}, "https://attacker.example/token")

    def test_wrong_recipient_in_mail_is_never_smtp_submitted(self):
        msg = build_email(self.article, JPEG, self.email)
        msg.replace_header("To", "attacker@example.com")
        with self.assertRaisesRegex(ValueError, "recipient_not_the_approved_sender"):
            gmail_submit(msg, self.email, "fake-test-only-value",
                         smtp_factory=FakeSMTP)
        self.assertEqual(FakeSMTP.sent, 0)



class FakePrivateContentsAPI:
    """No-network simulation of GitHub Contents API including SHA CAS."""
    def __init__(self):
        self.state = empty_private_ledger()
        self.sha = "initial-sha"
        self.conflict_next_put = False
        self.ack_without_write = False
        self.bad_receipt_next_put = False
        self.writes = 0

    def open(self, request, timeout):
        assert timeout == 20
        assert request.get_header("Authorization", "").startswith("Bearer ")
        assert "/repos/Hatem1984/RASD-Pilot/contents/delivery-state.json" in request.full_url
        if request.get_method() == "GET":
            assert request.full_url.endswith("?ref=rasd-private-delivery-state")
            body = {"sha": self.sha, "encoding": "base64",
                    "content": base64.b64encode(json.dumps(self.state).encode()).decode()}
            return io.BytesIO(json.dumps(body).encode())
        assert request.get_method() == "PUT"
        change = json.loads(request.data.decode())
        assert change["branch"] == "rasd-private-delivery-state"
        if self.conflict_next_put or change["sha"] != self.sha:
            self.conflict_next_put = False
            raise HTTPError(request.full_url, 409, "version conflict", {}, None)
        if self.ack_without_write:
            self.ack_without_write = False
            return io.BytesIO(json.dumps({"commit": {"sha": "fake-unpersisted-sha"}}).encode())
        new = json.loads(base64.b64decode(change["content"]))
        self.state = new
        self.sha = hashlib.sha1(change["content"].encode()).hexdigest()
        self.writes += 1
        if self.bad_receipt_next_put:
            self.bad_receipt_next_put = False
            return io.BytesIO(json.dumps({"commit": {}}).encode())
        return io.BytesIO(json.dumps({"commit": {"sha": self.sha}}).encode())


class GitHubPrivateLedgerTransportTests(unittest.TestCase):
    def test_real_read_reserve_commit_accept_and_readback_without_network(self):
        api = FakePrivateContentsAPI()
        with patch("delivery_bridge.build_opener", return_value=api):
            ledger = PrivateGitHubLedger("mock_token_nonsecret_123456")
            self.assertEqual(ledger.reserve(KEY, "sender@gmail.com"), "reserved")
            self.assertEqual(api.state["entries"][KEY]["status"], "reserved")
            self.assertEqual(ledger.reserve(KEY, "sender@gmail.com"), "manual_review_hold")
            receipt = "<rasd-" + KEY + "@gmail.com>"
            ledger.mark_smtp_accepted(KEY, receipt)
            restored, sha = ledger.read()
            self.assertEqual(restored["entries"][KEY]["status"], "smtp_accepted")
            self.assertEqual(restored["entries"][KEY]["message_id"], receipt)
            self.assertEqual(ledger.reserve(KEY, "sender@gmail.com"), "already_accepted")
            self.assertEqual(api.writes, 2)
            self.assertEqual(restored["approved_recipient_sha256"], APPROVED_HASH)


    def test_false_success_without_durable_reservation_never_sends(self):
        api = FakePrivateContentsAPI()
        api.ack_without_write = True
        with tempfile.TemporaryDirectory() as root, patch("delivery_bridge.build_opener", return_value=api):
            image = Path(root) / "capture.jpg"
            image.write_bytes(JPEG)
            ledger = PrivateGitHubLedger("mock_token_nonsecret_123456")
            FakeSMTP.sent = 0
            with self.assertRaisesRegex(RuntimeError, "private_ledger_commit_not_visible"):
                deliver_reserved({**ARTICLE, "publisher": "hapijournal.com",
                                  "selection": "live_feed_discovery"},
                                image, sender="sender@gmail.com",
                                approved_recipient="sender@gmail.com",
                                app_password="fake-test-only-value",
                                ledger=ledger, smtp_factory=FakeSMTP)
            self.assertEqual(FakeSMTP.sent, 0)
            self.assertEqual(api.state["entries"], {})

    def test_bad_github_commit_receipt_never_sends(self):
        api = FakePrivateContentsAPI()
        api.bad_receipt_next_put = True
        with tempfile.TemporaryDirectory() as root, patch("delivery_bridge.build_opener", return_value=api):
            image = Path(root) / "capture.jpg"
            image.write_bytes(JPEG)
            ledger = PrivateGitHubLedger("mock_token_nonsecret_123456")
            FakeSMTP.sent = 0
            with self.assertRaisesRegex(RuntimeError, "private_ledger_commit_receipt_invalid"):
                deliver_reserved({**ARTICLE, "publisher": "hapijournal.com",
                                  "selection": "live_feed_discovery"},
                                image, sender="sender@gmail.com",
                                approved_recipient="sender@gmail.com",
                                app_password="fake-test-only-value",
                                ledger=ledger, smtp_factory=FakeSMTP)
            self.assertEqual(FakeSMTP.sent, 0)
            self.assertEqual(api.state["entries"][KEY]["status"], "reserved")

    def test_smtp_accept_but_receipt_write_unverified_holds_without_resend(self):
        api = FakePrivateContentsAPI()
        with tempfile.TemporaryDirectory() as root, patch("delivery_bridge.build_opener", return_value=api):
            image = Path(root) / "capture.jpg"
            image.write_bytes(JPEG)
            ledger = PrivateGitHubLedger("mock_token_nonsecret_123456")
            FakeSMTP.sent = 0
            article = {**ARTICLE, "publisher": "hapijournal.com",
                       "selection": "live_feed_discovery"}
            params = dict(sender="sender@gmail.com",
                          approved_recipient="sender@gmail.com",
                          app_password="fake-test-only-value",
                          ledger=ledger, smtp_factory=FakeSMTP)
            # First persist a reservation, then fake a server success without a
            # durable acceptance receipt during the SMTP-completion stage.
            original_mark = ledger.mark_smtp_accepted
            def delayed_mark(key, receipt):
                api.ack_without_write = True
                return original_mark(key, receipt)
            with patch.object(ledger, "mark_smtp_accepted", side_effect=delayed_mark):
                with self.assertRaisesRegex(RuntimeError, "private_ledger_commit_not_visible"):
                    deliver_reserved(article, image, **params)
            self.assertEqual(FakeSMTP.sent, 1)
            self.assertEqual(api.state["entries"][KEY]["status"], "reserved")
            self.assertEqual(deliver_reserved(article, image, **params), "manual_review_hold")
            self.assertEqual(FakeSMTP.sent, 1)

    def test_private_ledger_token_rejects_wrong_mailbox_before_write(self):
        api = FakePrivateContentsAPI()
        with patch("delivery_bridge.build_opener", return_value=api):
            ledger = PrivateGitHubLedger("mock_token_nonsecret_123456")
            with self.assertRaisesRegex(ValueError, "recipient_not_approved"):
                ledger.reserve(KEY, "notapproved@gmail.com")
            self.assertEqual(api.writes, 0)

    def test_github_compare_and_swap_failure_blocks_smtp(self):
        api = FakePrivateContentsAPI()
        api.conflict_next_put = True
        with tempfile.TemporaryDirectory() as root, patch("delivery_bridge.build_opener", return_value=api):
            image = Path(root) / "capture.jpg"
            image.write_bytes(JPEG)
            ledger = PrivateGitHubLedger("mock_token_nonsecret_123456")
            FakeSMTP.sent = 0
            with self.assertRaisesRegex(RuntimeError, "private_ledger_request_failed"):
                deliver_reserved({**ARTICLE, "publisher": "hapijournal.com",
                                  "selection": "live_feed_discovery"},
                                 image, sender="sender@gmail.com",
                                 approved_recipient="sender@gmail.com",
                                 app_password="fake-test-only-value",
                                 ledger=ledger, smtp_factory=FakeSMTP)
            self.assertEqual(FakeSMTP.sent, 0)
            self.assertEqual(api.writes, 0)

    def test_full_mock_github_and_mock_smtp_only_once(self):
        api = FakePrivateContentsAPI()
        with tempfile.TemporaryDirectory() as root, patch("delivery_bridge.build_opener", return_value=api):
            image = Path(root) / "capture.jpg"
            image.write_bytes(JPEG)
            ledger = PrivateGitHubLedger("mock_token_nonsecret_123456")
            FakeSMTP.sent = 0
            article = {**ARTICLE, "publisher": "hapijournal.com", "selection": "live_feed_discovery"}
            options = {"sender": "sender@gmail.com", "approved_recipient": "sender@gmail.com",
                       "app_password": "fake-test-only-value", "ledger": ledger,
                       "smtp_factory": FakeSMTP}
            self.assertEqual(deliver_reserved(article, image, **options), "smtp_accepted")
            self.assertEqual(deliver_reserved(article, image, **options), "already_accepted")
            self.assertEqual(FakeSMTP.sent, 1)
            self.assertEqual(api.writes, 2)
            self.assertEqual(api.state["entries"][KEY]["status"], "smtp_accepted")


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
            self.assertEqual(result["healthy_sources"], 1)
            self.assertEqual(result["failed_sources"], 0)
            self.assertEqual(result["verified_publisher_links"], 1)
            self.assertEqual(result["planning_headline_matches"], 1)
            self.assertEqual(result["smtp_accepted"], 0)
            self.assertFalse(result["scheduler_enabled"])
            self.assertFalse(result["test_fixture_used"])

    def test_send_without_protected_authorization_fails_before_network(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "gmail_delivery_not_authorized"):
                credentials()

    def test_send_authorization_without_all_secrets_fails_closed(self):
        incomplete = {k: v for k, v in MANUAL_SEND_ENV.items()
                      if k != "RASD_PRIVATE_LEDGER_TOKEN"}
        with patch.dict(os.environ, incomplete, clear=True):
            with self.assertRaisesRegex(RuntimeError, "missing_protected_delivery_configuration"):
                credentials()

    def test_only_manual_dispatch_on_main_can_unlock_send(self):
        with patch.dict(os.environ, MANUAL_SEND_ENV, clear=True):
            self.assertEqual(credentials()["RASD_APPROVED_RECIPIENT"], "sender@gmail.com")
        for event, ref in (("schedule", "refs/heads/main"),
                           ("push", "refs/heads/main"),
                           ("workflow_dispatch", "refs/heads/develop"),
                           ("workflow_dispatch", "refs/tags/v1"),
                           ("", "refs/heads/main")):
            with self.subTest(event=event, ref=ref):
                environment = {**MANUAL_SEND_ENV,
                               "GITHUB_EVENT_NAME": event, "GITHUB_REF": ref}
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaisesRegex(RuntimeError,
                                                "gmail_delivery_requires_manual_main_dispatch"):
                        credentials()

    def test_github_rerun_cannot_reuse_past_mail_approval(self):
        for attempt in ("2", "3", "", "zero"):
            with self.subTest(attempt=attempt):
                e = {**MANUAL_SEND_ENV, "GITHUB_RUN_ATTEMPT": attempt}
                with patch.dict(os.environ, e, clear=True):
                    with self.assertRaisesRegex(RuntimeError,
                                                "gmail_delivery_requires_new_workflow_run"):
                        credentials()
        with patch.dict(os.environ, {**MANUAL_SEND_ENV, "GITHUB_RUN_ID": ""}, clear=True):
            with self.assertRaisesRegex(RuntimeError,
                                        "gmail_delivery_requires_new_workflow_run"):
                credentials()

    def test_other_repository_or_actor_cannot_send_using_cached_confirmation(self):
        variants = ({"GITHUB_REPOSITORY": "Other/RASD-Cloud-Monitor"},
                    {"GITHUB_ACTOR": "unapproved-collaborator"},
                    {"GITHUB_ACTOR": ""})
        for overrides in variants:
            with self.subTest(overrides=overrides):
                with patch.dict(os.environ, {**MANUAL_SEND_ENV, **overrides}, clear=True):
                    with self.assertRaisesRegex(RuntimeError,
                                                "gmail_delivery_requires_approved_repo_owner"):
                        credentials()

    def test_static_environment_secret_without_per_run_consent_fails_closed(self):
        for confirmation in ("", "YES_I_APPROVE_GMAIL_DELIVERY",
                             "CONFIRM_ONE_MANUAL_RASD_GMAIL_RUN "):
            with self.subTest(confirmation=confirmation):
                environment = {**MANUAL_SEND_ENV, "RASD_GATE11_RUN_CONFIRMATION": confirmation}
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaisesRegex(RuntimeError,
                                                "gmail_delivery_requires_per_run_confirmation"):
                        credentials()

    def test_preflight_never_grants_send_permission(self):
        environment = {k: v for k, v in MANUAL_SEND_ENV.items()
                       if k != "RASD_GATE11_SEND_APPROVED"}
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(credentials(require_send_approval=False)["RASD_GMAIL_USER"],
                             "sender@gmail.com")
            with self.assertRaisesRegex(RuntimeError, "gmail_delivery_not_authorized"):
                credentials()

    def test_wrong_sender_recipient_never_unlocks_manual_send(self):
        environment = {**MANUAL_SEND_ENV, "RASD_APPROVED_RECIPIENT": "different@gmail.com"}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(RuntimeError, "sender_recipient_identity_mismatch"):
                credentials()


if __name__ == "__main__":
    unittest.main()
