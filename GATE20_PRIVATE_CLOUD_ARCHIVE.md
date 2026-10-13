# RASD — Gate 20: private cloud evidence storage (staged, NOT provisioned)

**Decision:** Cloud-only RASD; final artifact **Word (.docx) only**, with actual browser screenshots of original publisher pages for every article. Owner Windows PC never hosts the monitor. Gmail and scheduling remain OFF.

## Confirmed blockers

The GitHub-hosted Chromium browser renders ordinary images successfully. Some original publisher article pages reject hosted requests with an access-refused HTTP response (401/403). A different storage provider does **not** resolve an access restriction; do not use rotating proxies, spoofing, CAPTCHA bypass, alternate copied images or synthetic screenshots. Obtain legitimate publisher access/terms clearance or add other separately reviewed accessible original-source publications. On publisher denial the final report remains HOLD.

## What this Gate adds

- `private_evidence_archive.py`: immutable content-addressed S3-compatible private storage; currently configured for Cloudflare R2 through an isolated owner-approved runner. One original JPEG per article (multiple identical bytes may share binary, but IDs remain distinct) and a final evidence-complete Word are uploaded privately.
- SHA-256 is checked for each JPEG, and every expected screenshot byte digest must exist inside the Word file itself.
- Each remote upload is retrieved and SHA-256 compared byte-for-byte. The final *commit manifest* is uploaded **LAST**, only if everything else matches. A partial failure leaves no approved manifest; orphaned private objects may require retention cleanup later.
- `cloud_proof_report.py` accepts an optional archive writer. A failed archive operation clears the local final Word, reports HOLD and logs no private cloud details.
- `private_proof_worker.py` validates exact repo, owner, workflow, branch, first attempt and per-run text confirmation **before accessing feeds, Chromium, R2 or any sensitive credential**.
- `.github/workflows/private-proof-manual.yml`: manual-only, separate protected environment; no Gmail, cron, client APK or EXE, no public news-image uploads.
- Offline contract tests use an in-memory Fake S3 and fake publisher screenshots. They **DO NOT** constitute a successful real cloud upload.

## Owner-only provisioning required before a live R2 test

1. Review Cloudflare R2's costs and terms. R2 requires an active R2 subscription even when usage falls inside a free monthly allowance. Do not subscribe or add payment details without explicit owner authorization.
2. In a Cloudflare account **after cost approval**, create a **private** bucket named for RASD. Disable public bucket URL and public custom-domain access. Arrange retention and permitted use rights for publisher screenshots.
3. In GitHub, create a new Environment named exactly `rasd-evidence-private-manual-approval`, with required reviewer `Hatem1984`, production `main` only, admin bypass disabled and deliberate self-review permitted if the sole owner.
4. Add only these **Environment secrets**, privately in the GitHub UI (never in chat):
   - `RASD_R2_ACCOUNT_ID`: 32-character lowercase Cloudflare account ID.
   - `RASD_R2_BUCKET`: exact private R2 bucket name.
   - `RASD_R2_ACCESS_KEY_ID`: restricted R2 token Access Key ID with minimum necessary bucket object permissions.
   - `RASD_R2_SECRET_ACCESS_KEY`: paired restricted R2 token secret.
   - `RASD_PRIVATE_ARCHIVE_ENABLED`: owner's deliberate opt-in phrase `YES_I_APPROVE_PRIVATE_RASD_EVIDENCE_STORAGE`.
5. Only after the above, a **separately approved single run** of `RASD Gate 20 — private original-publisher evidence archive (manual only)` can be dispatched on main with `archive_confirmation` set to `CONFIRM_ONE_PRIVATE_RASD_ARCHIVE_RUN`. It does not send emails, create billing subscriptions or schedule future runs. Replays, forks, different branches, missing credentials, and incorrect confirmation fail closed.

A successful manual job still requires all genuine publisher screenshots. An access-refused page results in HOLD and no finalized report/commit manifest. Private archived objects MUST later be served through a user-authenticated RASD API with authorization checks, not exposed as public bucket URLs or passed direct cloud credentials to APK/EXE.

## Current status

**Prepared in code and fake-S3 tested, not yet a working R2 deployment.** No R2 bucket, account, API, data migration or purchased service was created in this gate. The local cloud preview remains separate from screenshot-proof final Word. SMTP/Gmail delivery and recurring schedules remain unapproved.

Next gates after storage credentials and publisher permission: live upload/readback test, persistent article/job state + private retrieval API, then Android/Windows application clients.
