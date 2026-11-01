"""Fail-closed production recipient preflight, without network or mail.

Do not print recipient values, hashes, credentials, SMTP replies or private ledger.
Executed after dependencies are installed and BEFORE any scheduled private I/O.
"""
from __future__ import annotations
import os
from scheduled_rasd import approved_report_copy

def check() -> bool:
    if os.getenv("RASD_REPORT_CC_REQUIRED") != "true":
        return False
    sender = os.getenv("RASD_GMAIL_SENDER", "").strip().casefold()
    primary = os.getenv("RASD_REPORT_TO", "").strip().casefold()
    if not sender or not primary:
        return False
    try:
        return approved_report_copy(sender, primary) is not None
    except (RuntimeError, ValueError, TypeError):
        return False

def main() -> int:
    passed = check()
    print("RASD_PINNED_SECOND_RECIPIENT_SECRET_PREFLIGHT=" + ("PASS" if passed else "HOLD_NO_SEND"))
    return 0 if passed else 2

if __name__ == "__main__":
    raise SystemExit(main())
