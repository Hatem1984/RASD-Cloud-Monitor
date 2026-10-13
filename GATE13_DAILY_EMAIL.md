> **Superseding decision — 14 October 2026, Gate 19:** RASD outputs **Word (.docx) only**. PDF generation, PDF attachments and PDF uploads are retired. RSS-only Word files are explicitly named `RASD-Preview-YYYY-MM-DD.docx` and are NOT final reports. A final `RASD-Daily-YYYY-MM-DD.docx` is produced only after all included news items have validated screenshots of their original publisher webpages and coverage is healthy; otherwise the report is `HOLD`. The protected email workflow is manual-only and must not send incomplete reports. Content below includes historical pre-Gate19 acceptance notes for audit continuity.

# Gate 13 — Gmail delivery of Arabic daily Word and PDF (manual-only)

**Implemented code; offline acceptance PASSED. Gmail transport itself is NOT activated, NOT tested against real Gmail, and NOT scheduled.**

## Verified implementation

- Dedicated [manual Gmail digest workflow](.github/workflows/digest-mail-manual.yml) uses the existing protected GitHub environment `rasd-gmail-manual-approval` and its existing secret names. It adds no new provider, subscription, cron, storage service or credential.
- A single manually authorized invocation scans the two approved original publisher RSS feeds, produces one Arabic Word and one PDF in a temporary GitHub-hosted runner directory, checks both files open and have non-empty contents, and attaches both to **one** Gmail message addressed to the SAME pinned approved sender. It never uploads emailed attachments or receipts into the public repo.
- A deterministic `rasd-daily-report-v1:<Cairo calendar date>` hash is used as the private ledger key. **One automatic SMTP submission attempt per Cairo calendar day**. The same day cannot automatically send a second report even if headlines later change. An SMTP-accepted but non-durable receipt leaves the existing reservation in HOLD and forces manual Gmail Sent reconciliation.
- If both feeds fail, no report, private reservation or email is created. A single failure is shown as `DEGRADED`; no artificial news is invented. A zero-headline report can be sent **only when explicitly authorized**.
- Same account, no CC/BCC, no webhook, no third-party relay. `smtp_accepted` means only that the server accepted the message, not that inbox delivery was proven.

## Owner activation sequence — no secrets in chat

1. Complete [Gate 11 protected environment setup](GATE11_SECURE_SETUP.md) directly in your GitHub account. The connector currently lacks GitHub environment-admin/secret-write permissions. The original private repo remains private.
2. Leave the fifth environment secret `RASD_GATE11_SEND_APPROVED` **absent** until the owner separately authorizes a live email test. First run the existing protected `preflight` job without sending.
3. After preflight succeeds and the owner explicitly approves real delivery, create that fifth protected environment secret using the reviewed value in `gate11_runner.py`. Do not paste its value or any sensitive token into chat.
4. Go to [RASD Daily Report Gmail — manual owner-approved only](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/workflows/digest-mail-manual.yml), select branch `main`, and type the explicit `CONFIRM_ONE_MANUAL_RASD_GMAIL_RUN` into the `send_confirmation` input **for this individual run**. Approve the protected environment. GitHub rerun attempts are rejected.
5. Confirm **Sent and Inbox** contain exactly one copy of the message with **both** readable attachments, and that the separate private delivery ledger recorded the matching `smtp_accepted` Message-ID. On a network/ledger exception, inspect the private reservation before trying another run; NEVER reset or retry blindly.

## Security boundaries

The worker fails closed if the GitHub event is not a new owner-initiated `workflow_dispatch` on `main`, if the exact dedicated workflow reference differs, if confirmation or secret authorization is missing, if the account differs from the approved recipient, or if document validation fails. Secret inputs are passed only as protected job environment values; no SMTP error contents or email recipient strings are printed publicly.

No scheduled production mail is authorized by this change. Real delivery and inbox/readback remain OPEN until an actual user-approved live acceptance run succeeds. Only existing public GitHub Actions standard runners are used; no new paid connector or browser automation was started.
