# Gate 63 — unified Ministry Word MIME rehearsal, **NO SEND**

**18 October 2026 Cairo.** The RASD approved Stage2 artifact is `RASD-Unified-YYYY-MM-DD.docx`, constructed from the verified first-party Ministry NewsList, Hapi and **plural** original Al Masry RSS feed. This supersedes the earlier RSS-only daily Word path for the intended unified report, but does NOT authorize its delivery yet.

## Engineering finding

The older, protected `digest_mailer.py` still calls `cloud_proof_report.build_proof_report` and expects `RASD-Daily-YYYY-MM-DD.docx` plus a different `READY` audit schema. Its legacy SMTP ledger and picture-integrity tests, though useful, do not test delivery of the Stage2 **new unified Word**. **Do NOT use a successful old digest test as evidence the new three-source unified report was delivered.**

## Gate63 safe preparation

The new `gate63_unified_mail_no_send.py` performs *only* an in-process Gmail-MIME-format rehearsal using Python's standard `email.message.EmailMessage`:

- Requires a **completed** Cairo day (not today's partial day), matching Stage2 `READY_QA_ONLY` audit; 3 original named sources, all healthy, complete official source pagination, screenshot and Word evidence counts, exact original Ministry unified DOCX filename and 1–15 picture count.
- Requires public audit flags explicitly prove no email, schedule, private storage or publication were triggered. Rejects any unexpectedly changed source terms or source production promotion.
- Reads one ORIGINAL Word file in memory, validates it as readable DOCX and matches the declared article image count. Creates ONE Word MIME attachment, with the **exact same bytes**, and checks its media type/filename/payload SHA. No JPEG or Word is logged or uploaded.
- Uses fake `rasd-no-send-preflight@example.invalid` as both sender and recipient. No real account, Gmail OAuth/app-password, private ledger reservation, SMTP socket, API call, user email, R2 object or automatic scheduler exists in this helper. It returns only safe numeric counts, a SHA256 digest and `email_sent=false`.
- Deliberately **DOES NOT** claim independent replacement of Gate28/29 screenshot SHA binding, the Gate50 page-by-page render, original-source availability on two days, true owner visual review, Gmail authentication, SMTP acceptance or user Inbox delivery.

### Offline acceptance only

The tests feed the existing Gate40 **synthetic** Ministry+RSS unified Word, verify the exact one MIME attachment bytes in memory, and fail closed on bad source health, partial dates, altered safety flags, counts and old `RASD-Daily-...` filenames. Test mocks assert no SMTP call even if a module elsewhere exposes it. Synthetic Word does **not** represent a second real reporting day.

To test a real authorized machine-generated Word in a separate private workspace, provide its previously audited **SANITIZED** Stage2 JSON and matching already verified genuine Word file on that same trusted runner:

```text
python gate63_unified_mail_no_send.py --audit <private-audit.json> --word <private-RASD-Unified-YYYY-MM-DD.docx> --day YYYY-MM-DD
```

Do NOT place a genuine publisher Word or original screenshots into public GitHub Actions artifacts, PRs or repository commits. There is no new GitHub workflow and no production send job changed by this gate.

### Remaining production integration and release

A future, **separately approved** transport must securely generate/hold the *same* final trusted unified Word with original-publisher SHA receipts, real full-day + owner review acceptance, private recipient fingerprint and reservation/readback, owner-restricted protected GitHub environment, one-attempt SMTP/transport, and independent Gmail Sent/Inbox checks. A no-send MIME check is **NOT** a Gmail authentication test and cannot be converted into an active send merely by passing CI.

R2 bucket/provisioning, paid services and daily cron remain OFF. Stage2 issue #42 and original publisher malformed XML issue #53 remain OPEN until their distinct evidence requirements are met.
