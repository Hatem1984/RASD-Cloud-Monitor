# MA'AL / RASD — Production recovery acceptance, 27 Oct 2026

**Status: HOLD / do not merge or activate production.** This document captures proven behavior and incomplete release gates; it is not a claim of end-to-end live delivery.

## Baseline & evidence

- Live main: `9f6adcec3e8444bbc3eae940b8d5f62083be7551`.
- Independent pending changes: [#139](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/139) smart email, [#141](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/141) protected HOLD diagnostics, [#135](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/135) editorial QA, [#142](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/142) historical bundle integrity.
- This stacked [#143](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/143) reuses the PR #139 head and adds testable independent event-journal **contract**, not a second live worker or mailer.
- [Native run 40574342833](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/40574342833) produced an interval image HOLD status with `smtp_accepted=true` and later failed during combined interval/recovery; the final error was redacted as `other_held_failure`. It does not prove daily recovery is the cause without per-phase telemetry.
- [Cloudflare run 40575176605](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/40575176605): original publisher page refused, then `interval_status_already_reserved_or_sent`; combined job failed; no blind replay.
- Owner Inbox contained two half-hour *status* Word messages for the 27 Oct 22:30/23:00 local windows; actual source coverage and per-recipient delivery for other windows are **not** proven.
- Production legacy `send_empty_interval_status` intentionally creates an empty/status Word, reserves private CAS key, and invokes SMTP. This is the customer-visible root cause.
- Production `news_for_rollup` filters private mail delivery entries by `status=smtp_accepted` inside the previous 22:00-to-current-22:00 window. SMTP is not an evidence inventory, and this does **not** implement 00:00–22:00 source events plus late-night section.

## Work completed in isolated branch

- Existing `run_scheduled` code reused; smart-interval flag from PR #139 forwarded through the **existing** protected native GitHub scheduler, backup, and both Cloudflare dispatch jobs. The flag remains OFF in production until owner opts in. No cron/secret/recipient change was made.
- `rasd_event_journal.py`: validation contract independent of Gmail/SMTP, explicit original-page JPEG SHA-256 receipt + private immutable reference, HOLD separation, duplicate event identity, evidence-time classification, Egypt summer/winter Cairo boundaries, and one daily reservation with optimistic revision CAS. All effects are pure/in-memory; no private production backend is bound.
- Native interval worker exercised with isolated source/capture/transport mocks: 09:00 and 09:30 empty -> no send; 10:00 verified-branch result -> one send; 10:30 duplicate -> no send; 11:00 another new candidate -> one send. Missing original proof -> `EVIDENCE_HOLD`; ambiguous SMTP leaves CAS reserved and refuses retransmission.
- Event journal independently aggregates two synthetic verified-branch events at 22:00 even when SMTP is absent. 22:00–00:00 events go into a marked separate section on the NEXT day's report. This is **contract QA**, not live source durability or a 22:00 report dispatch.
- Report document renderer visual QA was run in an external isolated artifact sandbox with **synthetic** data and obvious watermarked synthetic images. DOCX JPEG media digests matched exact fixture bytes (2/2), and a three-page PDF was visually reviewed. Neither file is production news evidence.
- Owner local historical artifact for 17 October: `E:\MAAL\03_REPORTS_AND_REVIEW\MAAL_GATE_E_ACCEPTANCE_20261026\official-original.jpg` has SHA-256 `15b52a35e89f8ac0c8735b7fae8fafe36f0a11e772dc98a570d4f7bb24ef15d4`, equal to Word `word/media/image1.jpg` in the historical demo. This proves *that historical file pair's byte identity only*, not new/live events, new reporting, or Inbox receipt.
- PR #135 editorial historical QA manifest shows 17/24 Oct archive comparisons, explicitly no live re-verification; its reviewed output has 5 source-aware editorial sections but 0 original images. Therefore publication-grade current report remains HOLD.

## CI and local acceptance

- [CI 40580180540](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/40580180540): **613/613 PASS**, isolated Linux runner, no mail secrets, dry-run `smtp_sent=false`. Initial run failed from invalid synthetic test IDs/future winter fixture; those fixtures were corrected, no production files touched.
- [PR #141 CI 40577101194](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/40577101194): **591/591 PASS** for separate diagnostics (does not mean deployed).
- Owner Windows PR #139 isolated worktree: 8/8 focused smart no-empty tests PASS. Full suite on Python 3.14/Windows encountered bash subprocess unavailable for existing Linux-shell tests; this is environment incompatibility, not a local full-suite pass.

## Release blockers — mandatory

1. Implement/verify separate PRIVATE durable journal with independent CAS, immutable evidence JPEG storage, pinned image hashes, access controls, readback and recovery. A pure-state journal contract **is not** a live event store. Never store private originals or credentials in the public repository.
2. Wire only the already-reviewed producer success path **after** exact original publisher capture into that private journal, before optional SMTP. A storage failure must HOLD the candidate, not silently lose it. Backfill from independently verified original evidence only, never fabricate.
3. Bind the existing 22:00 rollup to a frozen journal snapshot; reconcile late-night and pending HOLD sections; render genuine JPEG from immutable private source; prove DOCX media hashes and paired PDF from identical snapshot. Distinguish event verification from editorial approval and SMTP.
4. Reconcile original private delivery CAS reservations and owner Gmail Sent/Inbox read-only. `smtp_accepted` != Inbox receipt. Uncertain reservations NEVER auto-resend.
5. Review PR #135 editorial source-grounded sections with original publisher proof and visual approval. Historical QA / synthetic image is insufficient.
6. Confirm cause of `other_held_failure` using PR #141 fixed-code/per-phase markers in an owner-approved safe release. Do not convert genuine failures to success or mask recovery HOLD.
7. Review published GitHub workflow logs for recipient-address exposure from repository `vars` versus secrets; migrate securely without dropping the authorized recipient (requires separate carefully planned change).

## One bounded rollout / rollback plan — NOT yet authorized

**Before release:** snapshot branch/commit, review both existing schedulers + Cloudflare relay, establish one approved release window, take read-only delivery and source-ledger snapshots, independently verify no reserved/uncertain SMTP duplicates, complete all blockers and secure owner approval.

**Deploy:** merge reviewed PR dependency chain in controlled order only after acceptance; first deploy dormant flag support with `RASD_SMART_NO_EMPTY_INTERVAL_EMAIL` unset, verify no changed recipients, schedules or CAS. Then owner enables **exact** repository variable `RASD_SMART_NO_EMPTY_INTERVAL_EMAIL=true` for a single monitored interval; observe `NO_NEW_VERIFIED_NEWS` / `EVIDENCE_HOLD`, no SMTP/CAS mutations; one genuine verified article still reaches only approved destination once. Activate independent journal-backed 22:00 path **only after** separate persistent-store + Word/PDF original-image acceptance. Keep existing daily path until formally replaced.

**Rollback:** unset/disable the smart flag, restoring previous legacy behavior; if code itself is faulty revert the reviewed release commit to pinned baseline via controlled PR, not a force push. Inspect private reservations/receipts FIRST. Do not delete journal events, alter original proof, or send reports as rollback. Note: rollback to legacy resumes noisy empty status messages, so prefer pausing affected mail entrypoint only with explicit owner decision if that behavior is unacceptable.

## Explicit owner approval still needed

- Approve merge/deployment and change window, secret handling and recipient reconciliation.
- Approve activating the flag and changing existing daily report input from accepted SMTP receipts to independently verified events.
- Editorially approve real original-image Word/PDF after visual sign-off and accurate coverage limitations.
- No approval is implied by reading this report. No production mail or schedule mutation performed here.
