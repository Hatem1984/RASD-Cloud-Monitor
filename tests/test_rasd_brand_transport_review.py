"""RASD display-brand migration: SMTP/IMAP routing invariants, offline only.

Review gate: subject changes must not alter approved recipients, copy,
Message-ID, delivery key, Word attachment, or Sent archive lookups.
No network and no real credentials are used.
"""
import hashlib
import os
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock, patch

import scheduled_rasd as rasd
from daily_sent_consolidator import original_sent_word
from digest_mailer import build_digest_message

SENDER = "rasd-sender@gmail.com"
RECIPIENT = "rasd-owner@example.org"
COPY = "rasd-approved-copy@example.org"
KEY = "9" * 24
MID = "<rasd-" + KEY + "@gmail.com>"
ATTACHMENT = b"unchanged-rasd-word-attachment-fixture"


class RasdBrandTransportReview(unittest.TestCase):
    def test_new_subject_preserves_exact_smtp_envelope_headers_and_attachment(self):
        client = MagicMock()
        client.send_message.return_value = {}
        factory = MagicMock()
        factory.return_value.__enter__.return_value = client
        allowed_copy = hashlib.sha256(COPY.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            word = Path(folder) / "RASD-News-With-Original-Screenshots.docx"
            word.write_bytes(ATTACHMENT)
            with patch.dict(os.environ, {"RASD_REPORT_CC": COPY}, clear=True), \
                 patch.object(rasd, "APPROVED_REPORT_COPY_SHA256", allowed_copy), \
                 patch.object(rasd.smtplib, "SMTP_SSL", factory), \
                 patch.object(rasd.ssl, "create_default_context",
                              return_value=MagicMock()):
                receipt = rasd.send_one_word(
                    word, sender=SENDER, recipient=RECIPIENT,
                    password="offline-only", subject="رصد | تقرير مراجعة",
                    key=KEY)
        self.assertEqual(receipt, MID)
        self.assertEqual(client.send_message.call_count, 1)
        message = client.send_message.call_args.args[0]
        self.assertEqual(message["Subject"], "رصد | تقرير مراجعة")
        self.assertEqual(message["From"], SENDER)
        self.assertEqual(message["To"], RECIPIENT)
        self.assertEqual(message["Cc"], COPY)
        self.assertEqual(message["Message-ID"], MID)
        self.assertEqual(message["X-RASD-Delivery-ID"], KEY)
        self.assertEqual(client.send_message.call_args.kwargs["to_addrs"],
                         [RECIPIENT, COPY])
        self.assertEqual(
            [part.get_payload(decode=True)
             for part in message.iter_attachments()], [ATTACHMENT])

    def test_sent_archive_reads_original_word_using_id_not_subject(self):
        for old_or_new in (
                "مآل | أخبار جديدة من الفحص الدوري",
                "رصد | أخبار جديدة من الفحص الدوري"):
            with self.subTest(subject_version=old_or_new.startswith("رصد")):
                message = EmailMessage()
                message["From"] = SENDER
                message["To"] = RECIPIENT
                message["Cc"] = COPY
                message["Subject"] = old_or_new
                message["Message-ID"] = MID
                message["X-RASD-Delivery-ID"] = KEY
                message.set_content("Offline RASD archive fixture")
                message.add_attachment(
                    b"W" * 4001, maintype="application",
                    subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                    filename="RASD-News-With-Original-Screenshots.docx")
                client = MagicMock()
                client.uid.side_effect = [
                    ("OK", [b"17"]),
                    ("OK", [(b"BODY", message.as_bytes())])]
                actual = original_sent_word(
                    client, MID, SENDER, RECIPIENT, approved_copy=COPY)
                self.assertEqual(actual, b"W" * 4001)
                self.assertEqual(client.uid.call_args_list[0].args,
                                 ("SEARCH", None, "HEADER", "Message-ID",
                                  '"' + MID + '"'))

    def test_manual_digest_subject_also_keeps_recipient_id_and_filename(self):
        report = {
            "email_sent": False, "scheduler_enabled": False,
            "private_state_used": False, "coverage": "HEALTHY",
            "status": "READY", "articles": 1, "screenshots_verified": 1,
            "screenshots_missing": 0, "word_created": True,
        }
        message = build_digest_message(
            report, "2026-11-07", KEY, ATTACHMENT, SENDER)
        self.assertTrue(message["Subject"].startswith("رصد | "))
        self.assertEqual(message["From"], SENDER)
        self.assertEqual(message["To"], SENDER)
        self.assertEqual(message["Message-ID"], MID)
        self.assertEqual(message["X-RASD-Digest-ID"], KEY)
        items = list(message.iter_attachments())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get_filename(), "RASD-Daily-2026-11-07.docx")
        self.assertEqual(items[0].get_payload(decode=True), ATTACHMENT)

    def test_duplicate_delivery_key_derives_from_slot_not_branding(self):
        self.assertEqual(rasd.digest_key("rollup:2026-11-07"),
                         hashlib.sha256(
                             b"rasd-scheduled-v1:rollup:2026-11-07"
                         ).hexdigest()[:24])
        self.assertEqual(rasd.digest_key("interval-status:2026-11-07T18:30Z"),
                         rasd.digest_key("interval-status:2026-11-07T18:30Z"))


if __name__ == "__main__":
    unittest.main()
