"""Read-only CAS + Gmail Sent integration QA; fake ledger & IMAP, never network."""
import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from docx import Document
from PIL import Image

from monitor import article_id
from rasd_verified_daily_archive_readonly import (
    _accepted_groups, accepted_web_daily_review)

DAY = date(2026, 11, 8)
NOW = datetime(2026, 11, 8, 21, 20, tzinfo=timezone.utc)
SENDER, RECIPIENT = "rasd.sender@gmail.com", "recipient@example.com"
MSG_ID = "<rasd-" + "a" * 24 + "@gmail.com>"
TOKEN, PASSWORD = "offline-token-not-real", "offline-password-not-real"


def sample():
    src = json.loads(
        (Path(__file__).resolve().parents[1] /
         "sources_newsroom_active.json").read_text(encoding="utf-8"))
    feed = src["feeds"][0]
    url = "https://" + feed["allowed_article_hosts"][0] + "/qa/synthetic-1"
    item = {
        "id": article_id(url), "url": url, "source": feed["name"],
        "headline": "خبر تجريبي لا يُمثل خبرًا منشورًا",
        "publisher_excerpt": "Synthetic evidence only",
        "published_at_cairo": "2026-11-08 20:05 EET",
        "published_display_cairo": "٨ نوفمبر ٢٠٢٦، الساعة ٢٠:٠٥",
    }
    state = {
        "schema_version": 2,
        "approved_recipient_sha256": hashlib.sha256(
            RECIPIENT.encode()).hexdigest(),
        "entries": {
            item["id"]: {
                "status": "smtp_accepted", "kind": "interval_item",
                "reserved_at": "2026-11-08T18:55:00+00:00",
                "accepted_at": "2026-11-08T19:00:00+00:00",
                "message_id": MSG_ID, "news": item,
            },
        },
    }
    return src, state, item


class FakeLedger:
    instance = None
    def __init__(self, token):
        assert token == TOKEN
        FakeLedger.instance = self
        self.calls = []
        self.state = sample()[1]

    def read(self):
        self.calls.append("read")
        return self.state, "private-get-read-sha"

    def write(self, *args, **kwargs):
        raise AssertionError("PRIVATE_LEDGER_WRITE_FORBIDDEN")

    def reserve(self, *args, **kwargs):
        raise AssertionError("PRIVATE_LEDGER_RESERVE_FORBIDDEN")


class FakeMail:
    def __init__(self):
        self.ops = []

    def login(self, sender, password):
        self.ops.append("login")
        assert sender == SENDER and password == PASSWORD
        return "OK", [b"accepted"]

    def list(self):
        self.ops.append("list")
        return "OK", [b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

    def select(self, name, readonly=False):
        self.ops.append(("select", readonly))
        return ("OK", [b"1"]) if readonly else ("NO", [])

    def logout(self):
        self.ops.append("logout")


class WebDailyReadOnlyQA(unittest.TestCase):
    def test_missing_credentials_fail_without_touching_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError,
                                        "readonly_archive_credentials_hold"):
                accepted_web_daily_review(
                    day=DAY, now=NOW, output=Path(folder),
                    sender="", recipient=RECIPIENT, app_password="",
                    ledger_token="")

    def test_existing_private_state_is_channel_web_only(self):
        cfg, state, item = sample()
        groups = _accepted_groups(state, DAY, cfg)
        self.assertEqual(groups, [(MSG_ID, [item])])
        state["entries"][item["id"]]["status"] = "reserved"
        self.assertEqual(_accepted_groups(state, DAY, cfg), [])

    def test_original_sent_images_to_web_daily_no_send(self):
        cfg, state, item = sample()
        archive = FakeMail()
        capture_calls = []
        def fake_mail_reader(client, mid, sender, recipient, *, approved_copy):
            self.assertEqual((mid, sender, recipient), (MSG_ID, SENDER, RECIPIENT))
            self.assertTrue(("select", True) in client.ops)
            capture_calls.append("original_sent_word")
            return b"synthetic-original-word"

        def fake_extractor(word_bytes, expected, output):
            self.assertEqual(word_bytes, b"synthetic-original-word")
            self.assertEqual(expected, [item])
            jpg = output / "source.jpg"
            Image.new("RGB", (500, 700), "white").save(jpg, "JPEG")
            return [(expected[0], str(jpg),
                     hashlib.sha256(jpg.read_bytes()).hexdigest())]

        with tempfile.TemporaryDirectory() as folder:
            result = accepted_web_daily_review(
                day=DAY, now=NOW, output=Path(folder) / "review",
                sender=SENDER, recipient=RECIPIENT,
                app_password=PASSWORD, ledger_token=TOKEN,
                ledger_factory=FakeLedger, client_factory=lambda: archive,
                message_reader=fake_mail_reader, extractor=fake_extractor)
            self.assertEqual(result["archive_status"],
                             "CAS_AND_READONLY_GMAIL_ORIGINALS_VERIFIED")
            self.assertEqual(result["reports"]["web-daily"]["items"], 1)
            self.assertEqual(result["reports"]["social-daily"]["items"], 0)
            self.assertEqual(result["reports"]["web-hourly"]["items"], 0)
            self.assertFalse(result["smtp_sent"])
            self.assertEqual(FakeLedger.instance.calls, ["read"])
            self.assertEqual(capture_calls, ["original_sent_word"])
            self.assertIn(("select", True), archive.ops)
            self.assertIn("logout", archive.ops)
            doc = Document(result["reports"]["web-daily"]["path"])
            self.assertEqual(len(doc.inline_shapes), 1)
            self.assertTrue(any(item["url"] == rel.target_ref for rel
                in doc.part.rels.values() if rel.reltype.endswith("/hyperlink")))

    def test_cli_rejects_non_ignored_private_output(self):
        import io
        import sys
        from unittest.mock import patch
        from rasd_verified_daily_archive_readonly import main
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(sys, "argv", [
                    "script", "--read-accepted-web", "--day", "2026-11-08",
                    "--out", str(Path(folder) / "public-output")]):
                with patch("sys.stdout", new_callable=io.StringIO) as text:
                    with self.assertRaises(SystemExit) as stop:
                        main()
                self.assertEqual(stop.exception.code, 1)
                self.assertIn("HOLD_OUTPUT_MUST_REMAIN_LOCAL_IGNORED",
                              text.getvalue())

    def test_wrong_approved_recipient_stops_before_imap(self):
        class WrongLedger(FakeLedger):
            def read(self):
                state, sha = super().read()
                state["approved_recipient_sha256"] = "0" * 64
                return state, sha
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError,
                                        "readonly_archive_recipient_not_approved"):
                accepted_web_daily_review(
                    day=DAY, now=NOW, output=Path(folder),
                    sender=SENDER, recipient=RECIPIENT,
                    app_password=PASSWORD, ledger_token=TOKEN,
                    ledger_factory=WrongLedger,
                    client_factory=lambda: self.fail("IMAP must not open"))


if __name__ == "__main__":
    unittest.main()
