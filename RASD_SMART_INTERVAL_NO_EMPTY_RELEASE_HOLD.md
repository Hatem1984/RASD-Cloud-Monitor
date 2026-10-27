# RASD/MA'AL — Smart 30-minute Delivery (isolated, NOT activated)

## Verified root cause
RASD production at main 9f6adce invokes `scheduled_rasd.send_empty_interval_status()` at two points:
1. no newly verified unsent articles found;
2. all matched articles fail genuine publisher-original screenshot capture.
That existing function creates a Word status attachment, reserves a new private CAS key, sends SMTP, and marks SMTP acceptance. This explains repeated zero-news/hold mail without implying duplicate news or Inbox delivery.

## Existing code reused, not replaced
Added a single opt-in guard to both existing interval branches:
`RASD_SMART_NO_EMPTY_INTERVAL_EMAIL=true`
- For zero eligible stories: `NO_NEW_VERIFIED_NEWS`, sends **zero** emails, never calls reserve or changes private CAS.
- For original-image HOLD: `EVIDENCE_HOLD` with counts and source failure count, no email/CAS mutation, and unaccepted news remains eligible for later retries.
- Normal intervals with verified original screenshot still follow existing send/CAS path; that path was not rewritten.
- Existing scheduler cron, zero-news daily 22:00 report and rollup remain UNCHANGED.
- Policy is OFF by default in this branch; production environment untouched. Activation requires explicit separate owner release approval plus comprehensive operator review.
- Run logs emit structured `RASD_SMART_INTERVAL_RESULT`; log retention follows GitHub Actions settings, not a new durable evidence store.

## Confirmed testing
- Eight dedicated offline tests PASS: no news/hold, no SMTP/CAS, repetition, malformed metadata, 22:00 Cairo DST and collision.
- 33 legacy schedule and half-hour status tests PASS with flag disabled; confirms backwards compatibility.
- 595 full offline repository regression tests PASS on this branch (Oct 27, no mail/network dispatch).
- Do not infer Inbox receipt from `smtp_accepted`; private recipient/inbox reconciliation is HOLD.

## Daily 22:00 gap
Current `news_for_rollup()` uses prior-day 22:00 → present 22:00 **and only SMTP-accepted interval_item ledger entries**, not all verification-qualified news between midnight and 22:00. Therefore the requested 00:00–22:00 daily accepted-event view and separate prior-night 22:00–00:00 section are NOT implemented yet. No production change to this fragile boundary without a verified unified event store, and no fabricated screenshots.

## Safe roll-forward / rollback decision
Required before activation:
1. Review exactly which existing schedulers trigger this function and any Cloudflare relay counterpart; do not create a parallel scheduler.
2. Validate full synthetic timeline (09:00,09:30,10:00,10:30,11:00,22:00) against existing private CAS adapter in a cloned, scrubbed lab.
3. Fix 22:00 accepted-events source safely, with Word embedded original image digest acceptance and DST/timezone tests.
4. Reconcile owner-authorized Inbox and private delivery ledger. SMTP != Inbox.
5. Obtain one explicit approval covering flag activation and change window, never edit live secrets/recipient manually.
6. Rollback: unset/disable `RASD_SMART_NO_EMPTY_INTERVAL_EMAIL`, preserving private ledger data, and review any sent status receipts before changes.

**Release status: HOLD / not owner or production accepted.**
