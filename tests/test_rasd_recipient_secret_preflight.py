"""RASD additional approved recipient: fail-closed migration tests.

Synthetic addresses only. No network, real credentials, recipients or SMTP.
"""
import hashlib
import os
import unittest
from unittest.mock import patch
import scheduled_rasd as rasd
import rasd_recipient_preflight as preflight

SENDER = "sender@example.com"
PRIMARY = "owner@example.com"
APPROVED = "synthetic-second@example.net"

class RecipientSecretSafety(unittest.TestCase):
    def setUp(self):
        p = patch.object(rasd, "APPROVED_REPORT_COPY_SHA256",
                         hashlib.sha256(APPROVED.encode()).hexdigest())
        p.start()
        self.addCleanup(p.stop)

    def test_mandatory_secret_absent_is_hold_before_delivery(self):
        with patch.dict(os.environ, {"RASD_REPORT_CC_REQUIRED": "true"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "report_copy_secret_missing"):
                rasd.approved_report_copy(SENDER, PRIMARY)
            self.assertFalse(preflight.check())

    def test_mandatory_secret_must_be_digest_pinned(self):
        env = {"RASD_REPORT_CC_REQUIRED": "true",
               "RASD_GMAIL_SENDER": SENDER, "RASD_REPORT_TO": PRIMARY,
               "RASD_REPORT_CC": APPROVED}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(rasd.approved_report_copy(SENDER,PRIMARY), APPROVED)
            self.assertTrue(preflight.check())
        env["RASD_REPORT_CC"] = "unauthorized@example.net"
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(preflight.check())

    def test_legacy_no_required_flag_remains_test_compatible(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(rasd.approved_report_copy(SENDER, PRIMARY))
            self.assertFalse(preflight.check())

    def test_preflight_never_returns_recipient_or_exception_message(self):
        with patch.dict(os.environ, {"RASD_REPORT_CC_REQUIRED": "true",
                                     "RASD_GMAIL_SENDER": SENDER,
                                     "RASD_REPORT_TO": PRIMARY,
                                     "RASD_REPORT_CC": "bad@invalid"}, clear=True):
            self.assertEqual(preflight.main(),2)

if __name__ == "__main__":
    unittest.main()
