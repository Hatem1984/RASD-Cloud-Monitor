# Gate 62 — local two-day owner evidence gate, NOT production delivery

As of **18 October 2026, 19:31 Cairo**, the second complete calendar day (18 October) is **NOT YET FINISHED**, so Stage 2 #42 cannot close. Only 17 October has an independently generated real 3/3 healthy Ministry + Hapi + original Al Masry plural RSS Word with original screenshot and machine render acceptance; two runs on that date still count as **ONE** date. Original publisher XML intermittence #53 remains OPEN.

## What this adds

The new **LOCAL-ONLY** command `gate62_two_day_owner_acceptance.py` can compare two *already locally decrypted* original genuine reports after the actual owner has completed **Gate61** page-by-page visual review, one for **each distinct completed Cairo date**. It verifies, independently for each day:

- Exact Word name/date, 3/3 approved original sources healthy, official archive cutoff complete and correct status, 1–15 original articles, exact original Word picture count, local page images and their SHA-256 manifest, disabled mail/cron/source promotion and production approval.
- Owner's deliberately entered **local** Gate61 self-attestation exists for that exact day and references the current exact Word and all its page hashes, page count, completed Cairo day, and a plausible local review timestamp. It explicitly refuses a forged claim of production approval or duplicate same-day runs.
- Two genuinely different completed Cairo dates with different original Word SHA, never just repeated builds of 17 October. Sorts dates, discloses only SHA and counts; it does not copy original articles, open a remote provider or read the RSA private key.

It returns `TWO_DISTINCT_FULL_CAIRO_DAYS_LOCALLY_SELF_ATTESTED_NOT_PRODUCTION_APPROVAL` **only** when BOTH independently pass. This means **self-attestation matched to the local evidence**, not cryptographic proof of reviewer identity or an actual approval of production. It is NOT allowed to set `human_visual_review=true` itself, produce a Word, send Gmail, provision R2 or create a schedule. All private files stay on the owner's computer.

## Instructions (PowerShell on owner's computer)

1. Download the original owner-only ciphertext for 17 October and any new successful second **complete** Cairo day after midnight 19 October; do not expose RSA private keys in GitHub, ChatGPT or external clouds.
2. Use the **existing** `gate43_owner_encrypted_review.py --decrypt` with the local original paired RSA private key separately for each day's artifact into **distinct** local folders. The existing script authenticates AES-GCM and page SHA receipts before writing any files.
3. Run `gate61_owner_private_visual_review.py --folder <private-folder> --day YYYY-MM-DD` for each day. Open its local `rasd-private-review-index.html` gallery and the original Word, inspect all pages, clipping, RTL Arabic, original dates/source and screenshots. Use `--attest` ONLY after actual human visual review of that day (interactive local TTY). An unattended/automated approval is invalid.
4. Verify both *real* locally self-attested reports:

```powershell
python gate62_two_day_owner_acceptance.py --folder-a "C:\RASD-Review\2026-10-17" --day-a 2026-10-17 --folder-b "C:\RASD-Review\2026-10-18" --day-b 2026-10-18
```

The command fails closed (`HOLD`) if either date is still partial, the required local attestation is absent, a screenshot/Word fingerprint differs, original-source health isn't full, or the same Cairo date is repeated.

## Important Stage 3/4/5 integration finding

**The legacy protected manual `digest_mailer.py` / `digest-mail-manual.yml` builds `RASD-Daily-YYYY-MM-DD.docx` through `cloud_proof_report.build_proof_report` (older RSS report).** It does **NOT** consume the Gate43/Gate58/Gate59/Gate60 validated **`RASD-Unified-YYYY-MM-DD.docx`** produced by the original Ministry + Hapi + plural Al Masry collector. Therefore its earlier offline Gmail tests **are not proof** that the current unified Stage2 Word is transport-ready. Do not enable the legacy send workflows as a substitute for a Stage2-complete actual product report. A separate future, explicitly approved no-send integration and real Gmail/ledger proof is still required.

**No automatic mail, R2 bucket, paid hosting, delivery schedule or production publication** is authorized by this new local acceptance checker. The original XML reliability issue #53 and Stage2 two-day/human proof #42 remain OPEN until actual real evidence and explicit owner review.
