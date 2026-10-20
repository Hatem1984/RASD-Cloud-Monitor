"""Gate70: NO SMTP, protected ledger, recipients or owner-signature spoofing."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from gate70_unified_word_delivery_no_send import (
    no_send_unified_delivery_contract, preview_legacy_key_conflict,
    unified_delivery_key,
)
from test_gate63_unified_word_mime_no_send import DAY, make_report


class UnifiedGmailNoSendContractTests(unittest.TestCase):
    def test_exact_same_original_word_owner_packed_sha_passes_no_send_only(self):
        with tempfile.TemporaryDirectory() as t:
            audit, word = make_report(t)
            with patch("smtplib.SMTP_SSL") as smtp:
                result = no_send_unified_delivery_contract(
                    audit, word, cairo_day=DAY,
                    owner_packed_sha256=hashlib.sha256(word.read_bytes()).hexdigest())
            smtp.assert_not_called()
            self.assertEqual(result["status"],
                             "UNIFIED_WORD_DELIVERY_CONTRACT_NO_SEND_ONLY")
            self.assertEqual(result["original_sources_verified"], 3)
            self.assertEqual(result["attachment_count"], 1)
            self.assertEqual(result["delivery_id"], unified_delivery_key(DAY))
            self.assertTrue(result["packed_original_word_identity_verified"])
            for name in ("mail_transport_implemented", "smtp_used",
                         "private_ledger_touched", "gmail_authenticated",
                         "owner_human_review_automated", "email_sent",
                         "r2_used", "scheduler_enabled",
                         "production_delivery_approved"):
                self.assertIs(result[name], False)
            self.assertNotIn("sha256", " ".join(result.keys()))
            self.assertNotIn("recipient", " ".join(result.keys()))

    def test_mutation_after_package_causes_hold(self):
        with tempfile.TemporaryDirectory() as t:
            audit, word = make_report(t)
            prior=hashlib.sha256(word.read_bytes()).hexdigest()
            body=word.read_bytes()
            word.write_bytes(body + b"tampered-owner-identity")
            with self.assertRaisesRegex(ValueError,
                                        "word_mismatch_owner_ciphertext"):
                no_send_unified_delivery_contract(
                    audit, word, cairo_day=DAY, owner_packed_sha256=prior)

    def test_missing_or_invalid_private_packed_sha_rejected(self):
        for bad in (None,True,"0"*63,"Z"*64,"wrong",5):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as t:
                audit,word=make_report(t)
                with self.assertRaisesRegex(ValueError,
                                            "packed_word_sha_missing"):
                    no_send_unified_delivery_contract(
                        audit,word,cairo_day=DAY,owner_packed_sha256=bad)

    def test_hold_or_bad_source_refused_before_no_send_contract(self):
        for change in ({"status":"HOLD"},
                       {"all_sources_healthy":False},
                       {"word_created":False},
                       {"email_sent":True},
                       {"source_added_to_production":True}):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as t:
                audit,word=make_report(t)
                audit.update(change)
                with self.assertRaisesRegex(ValueError,
                                            "stage2_not_qualified"):
                    no_send_unified_delivery_contract(
                        audit,word,cairo_day=DAY,
                        owner_packed_sha256=hashlib.sha256(word.read_bytes()).hexdigest())

    def test_wrong_date_or_wrong_file_format_refused(self):
        with tempfile.TemporaryDirectory() as t:
            audit,word=make_report(t)
            with self.assertRaisesRegex(ValueError,"audit_day_mismatch"):
                no_send_unified_delivery_contract(
                    audit,word,cairo_day=date(2026,10,19),
                    owner_packed_sha256=hashlib.sha256(word.read_bytes()).hexdigest())
        with tempfile.TemporaryDirectory() as t:
            audit,word=make_report(t)
            moved=word.with_name("RASD-Daily-2026-10-17.docx")
            word.rename(moved)
            with self.assertRaisesRegex(ValueError,"word_invalid"):
                no_send_unified_delivery_contract(
                    audit,moved,cairo_day=DAY,
                    owner_packed_sha256=hashlib.sha256(moved.read_bytes()).hexdigest())

    def test_unified_day_replay_key_is_stable_but_legacy_digest_is_not_same(self):
        a=unified_delivery_key(DAY)
        self.assertEqual(len(a),24)
        self.assertEqual(a,unified_delivery_key(DAY))
        self.assertFalse(preview_legacy_key_conflict(DAY))
        self.assertNotEqual(a,unified_delivery_key(date(2026,10,19)))

    def test_reject_non_date_identity(self):
        for x in ("2026-10-17",None,True):
            with self.assertRaisesRegex(ValueError,"invalid_cairo_day"):
                unified_delivery_key(x)

    def test_transport_plan_does_not_import_send_or_read_credentials(self):
        script=(Path(__file__).resolve().parents[1]/
                "gate70_unified_word_delivery_no_send.py").read_text()
        for banned in ("smtplib","smtp.login(","gmail_submit(",
                       "PrivateGitHubLedger","reserve_entry(",
                       "RASD_GMAIL_APP_PASSWORD","send_message(",
                       "urlopen(","boto3","requests."):
            self.assertNotIn(banned,script)


if __name__=="__main__":
    unittest.main()
