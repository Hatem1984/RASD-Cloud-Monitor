# Gate70 — Unified Word delivery identity and NO-SEND acceptance boundary

20 October 2026. Objective: remove the dangerous confusion between **legacy RSS-only `RASD-Daily-YYYY-MM-DD.docx`** in existing protected `digest_mailer.py` and **approved three-source unified Ministry `RASD-Unified-YYYY-MM-DD.docx`**. No real Gmail transport or private receipt ledger was used.

**Existing Gate63/64/65** already validate an in-memory MIME Word attachment, original publisher screenshots and its same-byte owner RSA/AES-GCM ciphertext identity. **New Gate70** adds an isolated future delivery identity and fail-closed contract on top of that existing proven code:

- Explicit SHA-256 comparison of the **original owner-encrypted Word** bytes and **the exact unified Word MIME attachment**. If either differs, HOLD before any transport.
- Stable 24-digit lowercase hex `delivery_id = sha256("rasd-unified-3-original-sources-word-v1:"+YYYY-MM-DD)[:24]` — intentionally domain-separated from the old RSS-only daily digest ledger ID `sha256("rasd-daily-report-v1:"+YYYY-MM-DD)[:24]`. The production private state is not read or changed by this module.
- Requires existing strong strict 3/3 source health, publisher screenshot/Word binding, completed Cairo day and max 15 news items.
- **Always** returns `UNIFIED_WORD_DELIVERY_CONTRACT_NO_SEND_ONLY`, `mail_transport_implemented=false`, `smtp_used=false`, `private_ledger_touched=false`, `production_delivery_approved=false`. The pure check cannot be tricked into approving Gmail or impersonating a human reviewer.

**Still outstanding for the later separately approved real Gmail stage:** genuine local Gate61/62 owner-human review; secure re-presentation of an approved report **without putting the owner's private RSA key on CI**; protected credentials and authorized recipient; private receipt reservation with compare-and-swap and anti-replay; a one-time explicitly consented SMTP submission; Sent/Inbox receipt reconciliation and post-send no-retry on uncertainty. Any live transport will require a new approved workflow and its own independent security tests — existing `digest-mail-manual.yml` MUST NOT be activated as if it delivers the new unified Word.

Stage2 original-source XML #53 and Stage2 owner review #42 are not closed by this contract. Production R2, cron, SMTP, source activation and public artifact upload remain OFF.
