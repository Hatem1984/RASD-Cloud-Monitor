# RASD — Gate 34: protected **read-only** private restore lane

**Date:** 18 October 2026  
**Engineering status:** implemented and tested against Fake-S3 only.  
**Live R2 status:** NOT PROVISIONED / NOT AUTHORIZED. Production storage Gate 34 remains **OPEN** until separate explicit owner consent and a real, private restore acceptance.

## Scope and controls

- New `private_restore_worker.py` and **manual-only** `.github/workflows/private-restore-manual.yml` perform a complete authorized `GET` verification of an existing private archive manifest, original Word and every original publisher JPEG.
- Worker calls the existing Gate 33 `restore_verified_bundle` in metadata-only mode. It verifies the exact privately held manifest SHA-256 and **all** restored Word/JPEG byte hashes, then revalidates article-order DOCX image relationships. Incomplete evidence is rejected.
- Must be first-attempt `workflow_dispatch` on `main`, initiated by `Hatem1984` from the exact named workflow, with **fresh typed confirmation** `CONFIRM_ONE_READONLY_RASD_RESTORE` and independently protected approval secret. A rerun, schedule, other actor, fork, missing secret, invalid date, malformed hash or wrong workflow fails **before an S3 client is constructed**.
- Uses `contents: read`, a separate owner-controlled environment `rasd-evidence-private-restore-approval`, and a **bucket-scoped READ-ONLY** R2 key. Do not reuse the write credential from the upload worker.
- Target manifest date and hash are **environment secrets**, not publicly visible workflow inputs. This path never creates a bucket, sends Gmail, uploads photos/Word as public GitHub artifacts, writes R2 objects, or enables cron.
- Public CI logs print only a small status/count result; no account ID, bucket, key, private manifest digest, Word, JPEG or article URLs. Failures are generic and fail closed.

## Before any genuine run — owner-controlled, **no action performed in this gate**

1. Separately approve any R2 account/subscription/billing and the handling/retention rights of original publisher-page evidence. Until approved, **stop**; offline Fake-S3 results are the only acceptance.
2. Create a private R2 bucket, locked-down network/permission policy, and a separate scoped **READ ONLY** object access key. Do not allow public/custom-domain bucket exposure. A future live write to produce a verified manifest also needs its own separate approval.
3. In GitHub repository `Settings → Environments`, create and protect `rasd-evidence-private-restore-approval`: restrict to `main`, require an authorized human reviewer, no admin bypass if supported. A missing environment must NOT be treated as production approval.
4. Enter environment **secrets directly in GitHub UI** (never in chat, public logs, PRs, files or workflow input fields):
   - `RASD_R2_RESTORE_APPROVED`: owner-controlled deliberate opt-in `YES_I_APPROVE_ONE_RASD_PRIVATE_RESTORE`
   - `RASD_R2_RESTORE_ACCOUNT_ID`: 32 lowercase hexadecimal characters
   - `RASD_R2_RESTORE_BUCKET`: exactly the provisioned private bucket
   - `RASD_R2_RESTORE_ACCESS_KEY_ID`: restricted **READ ONLY** key
   - `RASD_R2_RESTORE_SECRET_ACCESS_KEY`: paired key secret
   - `RASD_R2_RESTORE_MANIFEST_DATE`: date of an actual previously accepted private manifest, `YYYY-MM-DD`
   - `RASD_R2_RESTORE_MANIFEST_SHA256`: full 64-character SHA-256 of that private manifest, extracted from an authorized private record
5. After *separate* deliberate consent, manually dispatch the new workflow from `main`, enter the typed confirmation, and approve the environment. Inspect only the redacted status counts. This is NOT equivalent to a real Gmail send or production scheduler.

**Do not** dispatch the workflow to “try it” without an approved private manifest and explicit storage permission; even GET requests access private records and can have charges.

## Evidence available now

Offline [GitHub Actions CI](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39107125233) ran 191 tests, with one dependency-conditional skip. Tests cover verified Word+JPEG round-trip through a Fake-S3 reader that rejects ALL PUTs, corrupted and missing remote evidence, redacted result and authorization failures before opening the client. Current workflow does not enable any protected secrets, paid services, mail or scheduling.

## Remaining acceptance gates

- **Gate 34 live R2 HOLD:** explicit provider/cost/privacy approval; owner-provisioned protected environment, bucket/key, real original-publisher Word evidence written to private store, subsequent actual GET-only restore with SHA-256 and right-to-retain verification.
- **Gate 35:** protected Gmail preflight and later separately approved live transport/ledger replay.
- **Gate 36:** owner-approved scheduling, retries and incident notification.
- Authenticated API and downloadable clients only if included in final product scope.
