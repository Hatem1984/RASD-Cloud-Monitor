# RASD — Gate 35: verify actual Word attachment bytes before Gmail

**Date:** 18 October 2026  
**Scope:** offline-only Gmail transport hardening. **No real Gmail, private ledger, protected credentials, or scheduler activated.**

## Reproduced failure

The Gate 13 manual `deliver_digest` path validated the filename, ZIP readability and count of Word inline shapes. It did not independently check each Word picture's exact original-publisher capture SHA-256 **at the final transport boundary**. A Word with its JPEG bytes tampered after the initial report build, or a report missing its independent capture receipts, advanced to `ledger.reserve`.

[Test-first GitHub CI run 39107422050](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39107422050) reproduced **both** failures against mocked original-source RSS, fake Chromium captures and a ledger that forbids reservations: 193 tests, 2 intentionally failing cases, 1 conditional skip.

## Implemented fix

1. `verify_word` now parses the **same in-memory bytes** that would later become the one DOCX attachment, with a verified hard size limit.
2. Before `ledger.reserve`, the transport requires a full independent capture receipt list, one per selected article.
3. It validates the **exact attachment bytes** using the existing strict DOCX media relationship and ordered SHA-256 validator. A second filesystem read after validation is avoided by passing `BytesIO(attachment)` into the Word evidence validator.
4. Wrong/missing per-article JPEG evidence fails with `digest_word_evidence_integrity_failed`; there is **no private reservation, SMTP submission or automatic retry**.
5. Existing manual-only protected workflow, pinned approved sender/recipient, day-key anti-replay, at-most-one SMTP submission attempt, and all Gmail authorization requirements remain untouched.

A passing offline test does not imply delivery to Gmail Sent/Inbox, protected environment readiness, source-wide publisher coverage or scheduling acceptance. Those still require independent owner-approved live checks.

**Next:** real protected authentication-only Gmail preflight (no send) after provisioning; one separately approved live Word-only delivery with SHA/private receipt and Sent/Inbox reconciliation. No credentials should be pasted into GitHub issues, PRs, commits, chat or public logs.
