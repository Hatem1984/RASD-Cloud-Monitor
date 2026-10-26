"""One owner-authorized secondary recipient, one SMTP message, one ledger key.

No network, no credentials and no real Gmail calls.
"""
import hashlib
import os
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock, patch

import scheduled_rasd as worker
from daily_sent_consolidator import original_sent_word

SENDER = "reports.sender@gmail.com"
OWNER = "approved-owner@example.com"
COPY = "tarek.soliman1983@gmail.com"
KEY = "a" * 24
MID = "<rasd-" + KEY + "@gmail.com>"


class DualRecipientDeliveryTests(unittest.TestCase):
    def test_pinned_copy_address_and_fail_closed_for_others(self):
        with patch.dict(os.environ, {"RASD_REPORT_CC": COPY.upper()}, clear=True):
            self.assertEqual(worker.approved_report_copy(SENDER, OWNER), COPY)
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(worker.approved_report_copy(SENDER, OWNER))
        for unauthorized in ("random@gmail.com", OWNER, SENDER,
                             "tarek.soliman1983@gmail.com,other@example.org",
                             "invalid value"):
            with self.subTest(value=unauthorized), patch.dict(
                    os.environ, {"RASD_REPORT_CC": unauthorized}, clear=True):
                with self.assertRaisesRegex(RuntimeError,
                                            "report_copy_recipient_not_approved"):
                    worker.approved_report_copy(SENDER, OWNER)

    def test_one_smtp_envelope_two_recipients_same_word_and_id(self):
        client = MagicMock()
        client.send_message.return_value = {}
        smtp = MagicMock()
        smtp.return_value.__enter__.return_value = client
        with tempfile.TemporaryDirectory() as folder:
            word = Path(folder) / "RASD-word.docx"
            word.write_bytes(b"single-original-word-payload")
            with patch.dict(os.environ, {"RASD_REPORT_CC": COPY}, clear=True), \\
                 patch.object(worker.smtplib, "SMTP_SSL", smtp):
                received = worker.send_one_word(word, sender=SENDER,
                    recipient=OWNER, password="fake-not-sent",
                    subject="RASD professional Word report", key=KEY)
        self.assertEqual(received, MID)
        self.assertEqual(client.send_message.call_count, 1)
        msg = client.send_message.call_args.args[0]
        self.assertEqual(msg["To"], OWNER)
        self.assertEqual(msg["Cc"], COPY)
        self.assertEqual(msg["Message-ID"], MID)
        self.assertEqual(client.send_message.call_args.kwargs["to_addrs"],
                         [OWNER, COPY])
        self.assertEqual(len(list(msg.iter_attachments())), 1)
        self.assertEqual(next(msg.iter_attachments()).get_payload(decode=True),
                         b"single-original-word-payload")

    def test_no_copy_keeps_one_destination_and_partial_refusal_is_hold(self):
        client = MagicMock()
        client.send_message.return_value = {}
        smtp = MagicMock()
        smtp.return_value.__enter__.return_value = client
        with tempfile.TemporaryDirectory() as folder:
            word = Path(folder) / "RASD-word.docx"
            word.write_bytes(b"single-legacy-word-payload")
            with patch.dict(os.environ, {}, clear=True), \\
                 patch.object(worker.smtplib, "SMTP_SSL", smtp):
                worker.send_one_word(word, sender=SENDER, recipient=OWNER,
                                     password="offline", subject="RASD", key=KEY)
        self.assertIsNone(client.send_message.call_args.args[0]["Cc"])
        self.assertEqual(client.send_message.call_args.kwargs["to_addrs"], [OWNER])

        client.send_message.return_value = {COPY: (550, b"offline refused")}
        with tempfile.TemporaryDirectory() as folder:
            word = Path(folder) / "RASD-word.docx"
            word.write_bytes(b"one-word")
            with patch.dict(os.environ, {"RASD_REPORT_CC": COPY}, clear=True), \\
                 patch.object(worker.smtplib, "SMTP_SSL", smtp):
                with self.assertRaisesRegex(
                        RuntimeError, "smtp_uncertain_reconcile_sent_manually"):
                    worker.send_one_word(word, sender=SENDER,
                        recipient=OWNER, password="offline", subject="RASD", key=KEY)
        self.assertEqual(client.send_message.call_count, 2)  # no implicit retry

    @staticmethod
    def original_message(cc=None):
        msg = EmailMessage()
        msg["From"] = SENDER
        msg["To"] = OWNER
        if cc is not None:
            msg["Cc"] = cc
        msg["Message-ID"] = MID
        msg["X-RASD-Delivery-ID"] = KEY
        msg.set_content("Real Word stored in sender Sent mailbox")
        msg.add_attachment(b"D" * 4001, maintype="application",
                           subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                           filename="RASD-News-With-Original-Screenshots.docx")
        return msg.as_bytes()

    def test_sent_archive_accepts_old_and_new_only_without_extra_recipients(self):
        def imap_for(raw):
            client = MagicMock()
            client.uid.side_effect = [("OK", [b"17"]), ("OK", [(b"BODY", raw)])]
            return client
        self.assertEqual(len(original_sent_word(imap_for(self.original_message()),
                          MID, SENDER, OWNER, approved_copy=COPY)), 4001)
        self.assertEqual(len(original_sent_word(imap_for(self.original_message(COPY)),
                          MID, SENDER, OWNER, approved_copy=COPY)), 4001)
        for disallowed in (COPY, "another@example.net"):
            client = imap_for(self.original_message(disallowed))
            with self.assertRaisesRegex(RuntimeError,
                                        "daily_sent_message_headers_hold"):
                original_sent_word(client, MID, SENDER, OWNER)


if __name__ == "__main__":
    unittest.main()
