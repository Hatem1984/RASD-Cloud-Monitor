# MA'AL V0.3 — Historical Snapshot Sync, isolated pre-acceptance

## Scope
- Stacked on customer Round2 PR #138; original UI, styles, API reused, no alternate collector.
- Only with MAAL_HISTORICAL_SNAPSHOT_REVIEW=true on localhost does the existing product_report.json endpoint read a fixed owner-local current.json from E:/MAAL/04_HISTORICAL_QA/MAAL_UNIFIED_SNAPSHOT_REVIEW_20261027.
- Existing Gate E get_case() validates original JPEG SHA before the metadata-only refresh.
- Strict equality with the tracked Round2 baseline prevents unapproved report facts from entering UI; no verified source may be promoted through metadata writes.
- The existing V0.3 UI polls every 12 seconds, but explicitly separates review-package refresh from historical source publication and original screenshot observation. NEW VERIFIED EVENTS = 0.
- No email, no CAS, no production connector, no user approval or action.

## Actual QA evidence
- Seven new boundary tests PASS and 676/676 full repository tests PASS.
- Browser review refresh PASS: revision aec3f869e3bc9424c9 -> 4722a4eb5dc30b5d86, without page reload; two grouped historical signals unchanged.
- Tampered source claim returned HTTP 503, initial source snapshot restored, no JS errors.
- Owner-only proof: E:/MAAL/03_REPORTS_AND_REVIEW/MAAL_UNIFIED_SNAPSHOT_QA_20261027/snapshot_poll_and_tamper_proof.json.

## Limits and next work
- Snapshot is a HISTORICAL-only QA pipeline. Not the active RASD collector, never imply live source freshness.
- UI original Word/PDF downloads are still from the static Round2 review dataset. Same historical facts, but no revision-bound new-artifact generator. Bundle equality for genuinely new accepted news is NOT yet proven.
- Next: feed this fixed client/renderer contract via the existing G2 verified export, validated image/host/date and secured immutable revision. Build DOCX/PDF atomically and publish only after both hashes checked.
- Daily 00:00–22:00 accepted-event store, prior-night late events, email inbox receipt and full end-to-end still HOLD.
- Any production mail/cas/schedule changes require explicit owner approval.

Release: PARTIAL / NOT PRODUCTION READY.