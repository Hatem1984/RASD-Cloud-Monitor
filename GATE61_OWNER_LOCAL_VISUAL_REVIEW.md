# Gate 61 — review genuine decrypted Word pages on the owner's computer

**18 October 2026, Africa/Cairo. Stage 2 remains OPEN.** This is a small LOCAL convenience and safety gate, not a remote deployment, publisher change or production mail approval. Continue from Gate60 `6120a293997faeee3e7f13ed644f07c0e679d35a`.

## Why this is needed
The exact [successful full Cairo day 17 October Word run 39141231573, attempt 2](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39141231573/attempts/2) produced authenticated **owner encrypted-only** report Word + actual page PNG review artifact `12142165947` (expires **2026-10-19 15:43 UTC = 18:43 Cairo**). Another successful owner-only run [39139685216](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39139685216) produced artifact `12141530935` (expires Oct19 at **18:19 Cairo**). The real files are encrypted; CI must not have the owner's private RSA key. No authenticated human page-by-page visual review of either live Word has yet occurred.

The existing `gate43_owner_encrypted_review.py` ALREADY validates authenticated AES-GCM, ZIP member allowlists and SHA-256 PNG manifest, extracting only on the owner's computer. **Do not change or bypass it.**

The new `gate61_owner_private_visual_review.py` is intentionally a second, LOCAL-ONLY check and reviewer convenience. It reads an already decrypted true report. It verifies exact Cairo date and Word filename, genuine 3 original sources healthy, complete official pagination, owner-only encrypted render proof, 1–15 article count, exact source-photo vs Word embedded picture count, every individual page image and SHA-256, page manifest and delivery-disabling flags. It writes a private HTML gallery containing each exact original local page, in order, without JS, external images, fonts, analytics or network URLs. No image cropping, screenshot replacement, OCR or editing publisher text.

The script NEVER auto-marks human review as complete. With optional `--attest`, a reviewer must be at a **local interactive terminal**, actually inspect every Word page and the original Word, and explicitly type the exact printed confirmation phrase. Only then is a **local** no-overwrite `rasd-owner-human-review-attestation.json` created, recording report/page SHA-256 fingerprints and `production_delivery_approved=false`. This is **self-attested human evidence**, not a cryptographic identity signature and never automatic Stage2 closure. It does NOT rewrite the original private audit (which correctly stays `human_visual_review=false` to indicate pre-human cloud state).

## Owner workflow — genuine report, no secrets shared

First download the **RSA/AES-GCM ciphertext-only** artifact locally from the successful Github run before its 24-hour expiration; unzip to get `rasd-g43-owner-encrypted.json`. Keep the original owner's paired RSA private key on the owner computer. Run in PowerShell in a clone of this repository where Python dependencies are installed:

```powershell
python -m pip install -r requirements-test.txt
python gate43_owner_encrypted_review.py --decrypt --payload "C:\RASD-Review\rasd-g43-owner-encrypted.json" --private-key "C:\LOCAL-PRIVATE-KEY\owner-private.pem" --destination "C:\RASD-Review\2026-10-17"
python gate61_owner_private_visual_review.py --folder "C:\RASD-Review\2026-10-17" --day 2026-10-17
```

Open the generated **local** `C:\RASD-Review\2026-10-17\rasd-private-review-index.html`. Inspect each page in order for missing/clipped RTL Arabic headlines, small/illegible original publisher screenshots, original day/source, blank or duplicated pages, and compare the Word itself. If all pages are genuinely reviewed, use the separate final action:

```powershell
python gate61_owner_private_visual_review.py --folder "C:\RASD-Review\2026-10-17" --day 2026-10-17 --attest
```

Type the exact terminal challenge **only after** reviewing the original pages. No unattended commands, pipe-confirmation or ChatGPT-generated fake approval are valid. If the reviewer has NOT visually inspected the genuine pages, **do not use `--attest`**. Any source/image/HOLD/date mismatch, missing page or SHA mismatch stops before gallery creation.

**Sensitive data:** Keep the private key, decrypted Word, every PNG, review HTML and self-attestation file **ONLY on the owner's computer**. Never commit them, paste their contents into chat, upload to GitHub artifacts or a third-party app, or email before the delivery gate. Releasing the ciphertext link is safe; releasing decrypted content here is NOT approved.

## Stage2 acceptance boundaries

- At least TWO **distinct fully completed Cairo-calendar dates**, each with a genuine original-source 3/3-healthy report Word + all publisher screenshot SHA and render checks; separate *today partial* does not count.
- Owner or authorized human genuinely reviews the decrypted real Word and **every** image page, records local attestation. Synthetic crypto-loop tests cannot substitute for human.
- The intermittent malformed original publisher RSS Issue #53 remains OPEN: one healthy sample does not certify upstream stability.
- Stage2 Issue #42 remains OPEN until both distinct-date and human checks really happen.
- Gmail, cron, R2/private remote storage, new sources and production publication remain **OFF** and require separate later approval.

No paid service or runtime deployments were introduced by Gate61.
