"""Offline, credential-free tests for protected read-only Gate 11 preflight."""
import hashlib
import os
import unittest
from unittest.mock import patch

from gate11_preflight import preflight
from gate11_runner import credentials


ACCOUNT = "sender@gmail.com"
ENV = {
    "RASD_GMAIL_USER": ACCOUNT,
    "RASD_APPROVED_RECIPIENT": ACCOUNT,
    "RASD_GMAIL_APP_PASSWORD": "fake-test-only-value",
    "RASD_PRIVATE_LEDGER_TOKEN": "mock_token_nonsecret_123456",
    # The separate live-send consent is intentionally absent.
}
HASH = hashlib.sha256(ACCOUNT.encode()).hexdigest()


class MockPrivateLedger:
    reads = 0
    def __init__(self, token):
        assert token == ENV["RASD_PRIVATE_LEDGER_TOKEN"]

    def read(self):
        self.__class__.reads += 1
        return {"schema_version": 2, "entries": {},
                "approved_recipient_sha256": HASH}, "sha-from-private-ledger"


class MockSMTP:
    logins = 0
    sent = 0
    def __init__(self, hostname, port, timeout, context):
        assert hostname == "smtp.gmail.com" and port == 465
        assert timeout == 25
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def login(self, user, password):
        self.__class__.logins += 1
        assert user == ACCOUNT
        assert password == "fake-test-only-value"
    def send_message(self, *args, **kwargs):
        self.__class__.sent += 1
        raise AssertionError("preflight must never send email")
    def sendmail(self, *args, **kwargs):
        self.__class__.sent += 1
        raise AssertionError("preflight must never send email")


class PreflightTests(unittest.TestCase):
    def setUp(self):
        MockSMTP.logins = MockSMTP.sent = 0
        MockPrivateLedger.reads = 0

    def test_successful_preflight_reads_private_state_and_authenticates_without_mail(self):
        with patch.dict(os.environ, ENV, clear=True):
            result = preflight(ledger_factory=MockPrivateLedger,
                               smtp_factory=MockSMTP)
        self.assertTrue(result["approved_recipient_verified"])
        self.assertTrue(result["smtp_auth_verified"])
        self.assertEqual(result["smtp_sent"], 0)
        self.assertEqual(result["private_ledger_writes"], 0)
        self.assertFalse(result["scheduler_enabled"])
        self.assertEqual(MockSMTP.logins, 1)
        self.assertEqual(MockSMTP.sent, 0)
        self.assertEqual(MockPrivateLedger.reads, 1)

    def test_preflight_cannot_authorize_actual_send(self):
        with patch.dict(os.environ, ENV, clear=True):
            preflight(ledger_factory=MockPrivateLedger,
                      smtp_factory=MockSMTP)
            with self.assertRaisesRegex(RuntimeError, "gmail_delivery_not_authorized"):
                credentials()

    def test_missing_private_token_blocks_before_smtp(self):
        missing = {k: v for k, v in ENV.items() if k != "RASD_PRIVATE_LEDGER_TOKEN"}
        with patch.dict(os.environ, missing, clear=True):
            with self.assertRaisesRegex(RuntimeError, "missing_protected_delivery_configuration"):
                preflight(ledger_factory=MockPrivateLedger, smtp_factory=MockSMTP)
        self.assertEqual(MockSMTP.logins, 0)

    def test_substituted_mailbox_does_not_reach_smtp(self):
        wrong = {**ENV, "RASD_GMAIL_USER": "not-approved@gmail.com",
                 "RASD_APPROVED_RECIPIENT": "not-approved@gmail.com"}
        with patch.dict(os.environ, wrong, clear=True):
            with self.assertRaisesRegex(RuntimeError, "preflight_private_recipient_mismatch"):
                preflight(ledger_factory=MockPrivateLedger, smtp_factory=MockSMTP)
        self.assertEqual(MockSMTP.logins, 0)

    def test_bad_smtp_login_fails_closed_without_mail(self):
        class BadSMTP(MockSMTP):
            def login(self, user, password):
                raise ConnectionError("do-not-leak-sensitive-address-or-token")
        with patch.dict(os.environ, ENV, clear=True):
            with self.assertRaisesRegex(RuntimeError, "^preflight_smtp_auth_failed$"):
                preflight(ledger_factory=MockPrivateLedger, smtp_factory=BadSMTP)
        self.assertEqual(MockSMTP.sent, 0)

    def test_no_secret_fields_in_preflight_summary(self):
        with patch.dict(os.environ, ENV, clear=True):
            report = str(preflight(ledger_factory=MockPrivateLedger,
                                   smtp_factory=MockSMTP))
        self.assertNotIn(ACCOUNT, report)
        self.assertNotIn("fake-test-only-value", report)
        self.assertNotIn("mock_token_nonsecret", report)


if __name__ == "__main__":
    unittest.main()
