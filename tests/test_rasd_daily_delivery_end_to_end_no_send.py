"""Full RASD daily production-path QA with synthetic Sent mail, no network/send.

Uses real approved production functions: scheduled daily -> read authenticated
Sent Word (simulated IMAP) -> preserve authentic JPEG bytes -> new Ministry
visual Word -> validate exact MIME attachment/recipients -> durable CAS receipt.
Fixture JPEGs are fake and MUST NEVER be reported as real publisher evidence.
"""
from __future__ import annotations

import hashlib
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from docx import Document

import daily_sent_consolidator as archive
import scheduled_rasd as worker
from cloud_proof_report import word_images_match_capture_digests
from test_daily_sent_consolidation import (
    FakeSent, MergeActualDeliveredWord, SENDER, RECIPIENT
)


class MockTLSGmail:
    messages = []
    def __init__(self, host, port, timeout, context):
        assert (host, port) == ("smtp.gmail.com", 465)
        assert timeout == 25
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def login(self, sender, password):
        assert sender == SENDER and password == "offline-only"
    def send_message(self, message, from_addr, to_addrs):
        assert from_addr == SENDER
        assert to_addrs == [RECIPIENT]
        self.__class__.messages.append(message)
        return {}


class DailyProductionDeliveryNoSend(unittest.TestCase):
    def test_exact_originals_to_ministry_word_to_smtp_mime_and_duplicate_hold(self):
        helper = MergeActualDeliveredWord()
        MockTLSGmail.messages = []
        with tempfile.TemporaryDirectory(prefix="rasd-no-send-") as folder:
            root = Path(folder)
            stories = [helper.source_news(1), helper.source_news(2)]
            sent = {}
            state = {"entries": {}}
            hashes = {}
            for index, news in enumerate(stories):
                original, original_hashes = helper.sample_doc(root, [news])
                hashes.update(original_hashes)
                mid = "<rasd-" + ("c" if index == 0 else "d")*24 + "@gmail.com>"
                sent[mid] = helper.mail(mid, original)
                state["entries"][news["id"]] = {
                    "status": "smtp_accepted", "kind": "interval_item",
                    "news": news, "message_id": mid,
                }
            imap = FakeSent(sent)
            original_consolidator = archive.consolidate_sent_words
            capture_proofs = []
            def checked_consolidator(*args, **kwargs):
                kwargs["client_factory"] = lambda: imap
                word, proofs = original_consolidator(*args, **kwargs)
                self.assertTrue(word_images_match_capture_digests(word, proofs))
                capture_proofs.extend(proofs)
                return word, proofs

            ledger = MagicMock()
            ledger.read.side_effect = lambda: (state, "local-fixture-sha")
            def reserve(key, _recipient):
                if key in state["entries"]:
                    return "already_reserved"
                state["entries"][key] = {"status": "reserved"}
                return "reserved"
            ledger.reserve.side_effect = reserve
            def accepted(key, receipt):
                self.assertEqual(state["entries"][key]["status"], "reserved")
                state["entries"][key] = {
                    "status": "smtp_accepted", "message_id": receipt
                }
            ledger.mark_smtp_accepted.side_effect = accepted

            with (
                patch.dict(os.environ, {
                    "GITHUB_EVENT_NAME": "schedule",
                    "RASD_DAILY_SENT_ARCHIVE_ENABLED": "true",
                    "RASD_JOB_CRON": worker.DAILY_CRON,
                    "RASD_REPORT_CC": "",
                }),
                patch.object(worker, "require_github_scheduler"),
                patch.object(worker, "scheduled_phase", return_value="rollup"),
                patch.object(worker, "protected_credentials",
                             return_value=(SENDER, RECIPIENT, "offline-only", ledger)),
                patch.object(worker, "news_for_rollup", return_value=stories),
                patch.object(archive, "consolidate_sent_words",
                             side_effect=checked_consolidator),
                patch.object(worker.smtplib, "SMTP_SSL", MockTLSGmail),
            ):
                # Cairo 22:00 during November = 20:00 UTC.
                from datetime import datetime, timezone
                clock = datetime(2026, 11, 14, 20, 4, tzinfo=timezone.utc)
                outcome = worker.run_scheduled("rollup", clock)
                duplicate = worker.run_scheduled("rollup", clock)
            self.assertEqual(outcome["status"],
                             "daily_smtp_accepted_unconfirmed_inbox")
            self.assertEqual(outcome["items"], 2)
            self.assertEqual(duplicate["status"], "rollup_already_reserved_or_sent")
            self.assertEqual(len(MockTLSGmail.messages), 1)
            self.assertEqual(len(capture_proofs), 2)
            self.assertTrue(imap.selected_readonly)
            self.assertEqual(len(imap.searched), 2)
            self.assertEqual(imap.logout_count, 1)
            ledger.reserve.assert_called_once()
            ledger.mark_smtp_accepted.assert_called_once()
            self.assertEqual(ledger.mark_smtp_accepted_many.call_count, 0)

            msg = MockTLSGmail.messages[0]
            self.assertEqual(msg["To"], RECIPIENT)
            self.assertEqual(msg.get_all("Cc", []), [])
            self.assertEqual(msg["X-RASD-Delivery-ID"],
                             worker.digest_key("rollup:2026-11-14"))
            self.assertEqual(len(list(msg.iter_attachments())), 1)
            attachment = list(msg.iter_attachments())[0]
            self.assertEqual(
                attachment.get_content_type(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            self.assertEqual(
                attachment.get_filename(), "RASD-Daily-All-Delivered-News-Originals.docx")
            mail_word = root / "checked-attachment.docx"
            mail_word.write_bytes(attachment.get_payload(decode=True))
            doc = Document(mail_word)
            self.assertEqual(len(doc.inline_shapes), 2)
            self.assertGreaterEqual(len(doc.tables), 2)
            self.assertTrue(word_images_match_capture_digests(mail_word, capture_proofs))
            hyperlink_targets = {
                rel.target_ref for rel in doc.part.rels.values()
                if rel.reltype.endswith("/hyperlink")
            }
            self.assertTrue({a["url"] for a in stories} <= hyperlink_targets)
            with zipfile.ZipFile(mail_word) as z:
                pictures = [z.read(name) for name in z.namelist()
                            if name.startswith("word/media/")]
                self.assertEqual(len(pictures), 2)
                self.assertEqual(
                    {hashlib.sha256(p).hexdigest() for p in pictures},
                    set(hashes.values())
                )

    def test_no_email_when_consolidation_fails_before_reservation(self):
        ledger = MagicMock()
        ledger.read.return_value = ({"entries": {}}, "sha")
        rows = [MergeActualDeliveredWord().source_news(1)]
        with (
            patch.dict(os.environ, {
                "GITHUB_EVENT_NAME": "schedule",
                "RASD_DAILY_SENT_ARCHIVE_ENABLED": "true",
                "RASD_JOB_CRON": worker.DAILY_CRON,
            }),
            patch.object(worker, "require_github_scheduler"),
            patch.object(worker, "scheduled_phase", return_value="rollup"),
            patch.object(worker, "protected_credentials",
                         return_value=(SENDER, RECIPIENT, "offline-only", ledger)),
            patch.object(worker, "news_for_rollup", return_value=rows),
            patch.object(archive, "consolidate_sent_words",
                         side_effect=RuntimeError("daily_imap_archive_unavailable_hold")),
            patch.object(worker.smtplib, "SMTP_SSL",
                         side_effect=AssertionError("SMTP must not be attempted")),
        ):
            from datetime import datetime, timezone
            with self.assertRaisesRegex(RuntimeError,
                                        "daily_imap_archive_unavailable_hold"):
                worker.run_scheduled(
                    "rollup", datetime(2026, 11, 14, 20, 4, tzinfo=timezone.utc))
        ledger.reserve.assert_not_called()
        ledger.mark_smtp_accepted.assert_not_called()


if __name__ == "__main__":
    unittest.main()
