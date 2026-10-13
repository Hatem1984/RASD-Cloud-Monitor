"""Gate 11 private protected preflight: verify configuration, NEVER send email.

The operator first approves a GitHub environment-protected job. This process
reads the private state, checks the independent recipient fingerprint, then
authenticates to Gmail SMTP over TLS. It never commits state and never invokes
SMTP.send_message / sendmail / Gmail API send.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import smtplib
import ssl

from delivery_bridge import PrivateGitHubLedger
from gate11_runner import credentials


def preflight(*, ledger_factory=PrivateGitHubLedger,
              smtp_factory=smtplib.SMTP_SSL) -> dict:
    options = credentials(require_send_approval=False)
    account = options["RASD_GMAIL_USER"]
    if not account or not account.lower().endswith("@gmail.com"):
        raise RuntimeError("preflight_sender_invalid")
    state, sha = ledger_factory(options["RASD_PRIVATE_LEDGER_TOKEN"]).read()
    verified_digest = hashlib.sha256(account.strip().casefold().encode("utf-8")).hexdigest()
    if not hmac.compare_digest(verified_digest, state["approved_recipient_sha256"]):
        raise RuntimeError("preflight_private_recipient_mismatch")
    if not sha:
        raise RuntimeError("preflight_private_commit_unknown")
    try:
        with smtp_factory("smtp.gmail.com", 465, timeout=25,
                          context=ssl.create_default_context()) as smtp:
            smtp.login(account, options["RASD_GMAIL_APP_PASSWORD"])
            # Intentionally NO send_message, sendmail, or any mail construction.
    except Exception:
        raise RuntimeError("preflight_smtp_auth_failed") from None
    return {
        "mode": "preflight",
        "private_ledger_read": True,
        "approved_recipient_verified": True,
        "smtp_auth_verified": True,
        "smtp_sent": 0,
        "private_ledger_writes": 0,
        "scheduler_enabled": False,
    }


def main():
    try:
        print(json.dumps(preflight()), flush=True)
    except Exception:
        # Deliberately avoid exception text from SMTP servers or auth provider.
        print("gate11_preflight_failed_closed", flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
