# Gate 58 — Manual Stage 2 genuine Word: truthful acceptance and Cairo-day separation

**Date:** 18 October 2026 (Africa/Cairo). Continuation from merged Gate57 `9f88baf95068aaa91d454399d05d4034b9cc7bf0`. Stage 2 is **NOT** fully accepted.

## Why this gate is needed

The existing production-disabled `.github/workflows/report-unified-ministry-manual.yml` successfully encrypted an **audit-only HOLD** (e.g., intermittent malformed native Al Masry Al Youm RSS), but the workflow could still show a misleading green orchestration result. Also its existing `today` option intentionally observes an **incomplete** Cairo day, and must never be credited towards the two full-day acceptance requirement.

Gate58 changes only the protected manual acceptance classification and evidence handling. It does **not** change `sources.json`, the saved four Ministry words, live RSS parsing, publisher domain rules, original article identity/date, Word/JPEG contents, production email, R2 or cron.

## Acceptance outcomes (never final human approval)

| Input / evidence | Word package | GitHub workflow conclusion | Acceptance |
|---|---|---|---|
| `yesterday`, 3/3 original healthy, original-image SHA verified, full private Word render, encrypted pages | Owner ciphertext containing genuine Word/pages | Green | `READY_QA_ONLY` — **machine accepted, human review pending** |
| `yesterday`, malformed mandatory RSS or any source/image/proof HOLD | Owner-encrypted audit only, **NO Word** | **Red** | `HOLD` |
| `today`, even if source/page checks all pass | Owner-encrypted **partial-day QA-only**, never delivery | **Red for full-day acceptance** | `PARTIAL_QA_ONLY` |
| Missing/invalid ciphertext or unsafe state | No trusted deliverable | **Red** | Failure; no source or owner approval |

The public GitHub Action uploads only its existing RSA/AES-GCM ciphertext file; one-day expiry. When the Word collector is an explicit source HOLD, upload **still runs** and the final acceptance check returns RED rather than green. When conversion, cryptographic packaging or local integrity validation crashes, a red run is mandatory and plaintext remains unuploaded.

### Independent offline tests

`tests/test_gate58_manual_word_machine_acceptance.py` checks correct Cairo date selection; today's not-full-day result; source HOLD; no Word in HOLD; Word/JPEG/source/owner encrypted-page integrity; prohibited mail, cron, source change, plaintext; an invalid dispatch choice or date mismatch; and branch/main-only/manual-only workflow contract. Existing regressions still run through the main security CI.

### How to test the **second distinct complete Cairo day**

The existing first real full-day successful report is **17 October 2026**, proved by Gate57 [39136961587](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39136961587) with `READY_QA_ONLY`. It is **not** owner-human-approved.

**Only on or after 19 October 2026, Cairo-local midnight**, the repository owner can manually select **Actions → RASD Ministry official + RSS — manual strict Word owner review (NO Gmail) → Run workflow → main → yesterday**. That collects the **18 October 2026** complete calendar day if it remains eligible under the bounded live original sources. It does not schedule itself, make network requests in the background or dispatch any email.

**Never claim second-day acceptance just because CI is green.** Inspect both the job conclusion and audit in the owner-encrypted bundle. Today's live RSS feeds remain rolling and may not contain a complete prior-day inventory; report holds whenever coverage cannot be certified. A separate human review of *every* decrypted true Word page is required.

### Owner-only visual review

Download the successful encrypted artifact before its one-day expiry. On the owner's **local** Windows computer only, use the repository's existing `gate43_owner_encrypted_review.py --decrypt --payload <local-encrypted-json> --private-key <local-original-RSA-private-key> --destination <local-private-folder>`, never pasting or uploading the private key. The unpacker validates archive filenames and page hashes before writing any plaintext. Open each `review-pages/page-NNN.png` in order and the original `RASD-Unified-YYYY-MM-DD.docx`, inspect RTL Arabic headlines, original dates and publisher evidence readability, all page breaks, blank/clipped pages, and the number of article screenshots. A cryptographic or machine green result is **not** a human visual signature.

Keep Stage2 #42 and malformed-source #53 open. No production source promotion, storage, Gmail or cron may be turned on until separate later approvals.
