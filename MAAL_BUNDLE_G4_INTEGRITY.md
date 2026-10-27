# MA'AL | Snapshot → historical owner-report bundle integrity (isolated Gate G4)

**Date:** 27 October 2026
**Branch:** `feat/maal-snapshot-report-bundle-integrity-20261027` (stacked on PR #140; do not merge into main)
**Development worktree:** `E:\MAAL\01_ACTIVE_CODE\MAAL_SNAPSHOT_BUNDLE_GUARD_20261027`

## Scope and rationale

The V0.3 preview already presents a historical owner-review data snapshot and static Word/PDF reports. Previously it could serve these as unrelated assets. This branch adds an explicit **fail-closed byte-level link** between the reviewed historical snapshot revision, canonical JSON content and the exact existing Word and PDF bytes.

- `maal/report_bundle_guard.py`: versioned integrity schema and immutable content digest, revision lock and both artifact SHA-256 checks.
- `maal_web/server.py`: opt-in `/api/report-bundle` status and guarded `/reports/...pdf|docx` routes; returns 503 when referenced artifacts, revision or snapshot facts differ. All code remains on 127.0.0.1, with no new POST workflow.
- `tests/test_maal_report_bundle_integrity.py`: 12 portable synthetic positive/negative cases; protects against altered facts, altered revisions, tampered/missing files, invented current-news status or delivery success, upgraded unverified source images, and malformed files.
- Owner-local private attestation and real-file QA: `E:\MAAL\04_HISTORICAL_QA\MAAL_BUNDLE_PARITY_20261027`. **Do not commit it or the report binaries**.

## Locally verified reviewed baseline

- Staged snapshot review revision: `4722a4eb5dc30b5d86`.
- Official source documents 17, 24 and 26 October 2026; **ONLY** 17 October has independently verified original JPEG and SHA in Gate E. 24 and 26 remain HOLD.
- Word file is static existing 38,144 bytes, PDF existing 71,841 bytes and four PDF pages.
- Source identifiers 7269, 7275 and 7276 and official figures 5,000 and 401.9 were found in **both** existing Word/PDF text layers during read-only QA.
- Both artifacts were downloaded via opt-in HTTP and their bytes SHA-256 verified against the pinned local attestation.
- New UI refresh and prior reviewed owner artifacts **are NOT auto-regenerated together**. This branch *blocks* a changed revision until a freshly reviewed pair and attestation exists; it does not claim dynamic document regeneration.
- No claims of new 27 October accepted news, customer funding eligibility, inbox receipt, or verified live RSS ingestion.

## Runtime
For this isolated branch only:
```powershell
$env:MAAL_HISTORICAL_SNAPSHOT_REVIEW = 'true'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -X utf8 E:\MAAL\01_ACTIVE_CODE\MAAL_SNAPSHOT_BUNDLE_GUARD_20261027\maal_web\server.py 52332
```

Preview: `http://127.0.0.1:52332/` (on owner computer only).
Status: `http://127.0.0.1:52332/api/report-bundle`.

## Acceptance and release blockers

- Synthetic unit and full RASD regression: separate acceptance log.
- HTTP only serves report assets when both SHA-256 digests and approved snapshot revision match.
- Public CI must run synthetic tests without private owner artifacts (no fabricated media).
- Gate H human review of its distinct DRAFT remains **HOLD**. Do not approve or execute it through this report-release branch.
- No production RASD/Gmail/CAS/schedules or email recipient changes. No PR merge, paid service, or cost.

## Competition handoff
Confirmed: reviewed historical two-signal report has paired source metadata+PDF+Word integrity guard and a read-only acceptance endpoint. Still not confirmed: live newsroom RASD → verified new screenshot → continuous AI → fresh owner-approved Gate H task → dynamic Word/PDF produced from the identical newly verified revision → inbox receipt.

## Verified result (post-change)
- 12/12 new synthetic digest/revision/claim/tamper tests PASS.
- Entire legacy RASD + MA'AL integration worktree suite **688/688 PASS** (32.388s), under Windows + Git Bash PATH; pre-existing simulated warnings have no failing assertions.
- Real localhost 52332 /api/report-bundle HTTP 200 with revision 4722a4eb5dc30b5d86; Word 38,144 bytes and PDF 71,841 bytes downloaded via verified routes; both SHA-256 match owner-private acceptance manifest.
- Four-page PDF and Word text layers independently contain original IDs 7269/7275/7276 and source figures 5,000/401.9. No claim that non-verified 24 or 26 October screenshots exist.
- New independent synthetic-only GitHub Actions workflow is explicitly scoped to this stacked branch, excludes all private report bytes.
