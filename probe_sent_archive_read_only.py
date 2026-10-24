"""ONE owner-authenticated read-only test of the existing private Gmail Sent archive.

No new SMTP, no Gmail state mutation, no archive in public CI artifacts, no
message subjects, URLs, email addresses, passwords, or blobs in public logs.
"""
from __future__ import annotations

import imaplib
import ssl
import tempfile
from collections import defaultdict
from pathlib import Path

from daily_sent_consolidator import (
    original_sent_word, sent_mailbox, extract_sent_originals,
)
from scheduled_rasd import protected_credentials


def main() -> None:
    sender, recipient, password, ledger = protected_credentials()
    state, _ = ledger.read()
    groups = defaultdict(list)
    for item in state["entries"].values():
        if (item.get("kind") == "interval_item"
                and item.get("status") == "smtp_accepted"):
            groups[item["message_id"]].append(item["news"])
    if not groups:
        print("RASD_SENT_ARCHIVE_PROBE=HOLD_NO_ORIGINAL_INTERVAL_DELIVERIES")
        raise SystemExit(2)
    msgid, originals = next(iter(groups.items()))
    try:
        with tempfile.TemporaryDirectory(prefix="rasd-sent-archive-probe-") as tmp:
            client = imaplib.IMAP4_SSL(
                "imap.gmail.com", 993,
                ssl_context=ssl.create_default_context(), timeout=25)
            try:
                status, _ = client.login(sender, password)
                if status != "OK":
                    raise RuntimeError("login_rejected")
                sent_mailbox(client)
                data = original_sent_word(client, msgid, sender, recipient)
                proven = extract_sent_originals(data, originals, Path(tmp))
                if len(proven) != len(originals):
                    raise RuntimeError("archive_content_integrity")
            finally:
                try:
                    client.logout()
                except Exception:
                    pass
        print("RASD_SENT_ARCHIVE_PROBE=VERIFIED_READ_ONLY"
              f" ARTICLE_ORIGINAL_IMAGES={len(originals)}"
              " EMAILS_SENT=0 PRIVATE_LEDGER_WRITES=0")
    except Exception as err:
        # Deliberately suppress raw IMAP responses, account details and tokens.
        print("RASD_SENT_ARCHIVE_PROBE=HOLD"
              f" FAILURE_TYPE={type(err).__name__}"
              " EMAILS_SENT=0 PRIVATE_LEDGER_WRITES=0")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
