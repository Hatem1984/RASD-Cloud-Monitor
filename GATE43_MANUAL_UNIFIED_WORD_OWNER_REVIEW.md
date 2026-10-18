# RASD Gate 43 — Ministry + RSS official daily Word: manual owner-only encrypted review

**Operating scope:** Egyptian Ministry of Planning ONLY. Keep the four saved OR phrases in `sources.json`, unchanged: `وزارة التخطيط`, `وزير التخطيط`, `وزيرة التخطيط`, `التخطيط والتنمية الاقتصادية`.

## What is activated

A standalone **owner-initiated manual**, unscheduled and no-email workflow:

`.github/workflows/report-unified-ministry-manual.yml`

It runs the exact original-source pipeline in `unified_ministry_word.py`:
1. Two trusted original publisher RSS feeds (Hapi, Al Masry Al Youm), both required healthy.
2. The official Ministry site `mped.gov.eg` real first-party `News/NewsList` with bounded pagination and verifiable original dates. The source is activated **only in this manual complete-proof collector**, not in the old headline-only RSS preview or any scheduled sender.
3. One Cairo local day: `yesterday` (complete calendar day) or `today` (in-progress/partial, never called full-day delivery).
4. A *single* `RASD-Unified-YYYY-MM-DD.docx` Word when all original pages, exact saved terms, dates, JPEG proof, ordered embedded SHA-256 digests and max-15 cap are valid.
5. Ephemeral private LibreOffice render-to-PDF-to-page-PNG mechanical preflight, including image constraints and blank-page rejection; **not** human page-by-page review.
6. The full Word and the redacted report audit encrypted for the owner, with the existing `gate26_owner_review_pubkey.pem` public key. Only encrypted JSON is uploaded to GitHub Actions as a one-day artifact. No plaintext Word/JPEG/PNG/PDF uploaded. The private RSA key never enters GitHub.

If a source fails or one picture is incomplete: **HOLD, no Word inside the encrypted package**. It contains sanitized counts/audit only. No email, scheduled task, R2 or production recipient state is touched.

## How owner starts actual review, no secrets in chat

1. On GitHub, open **Actions** for `Hatem1984/RASD-Cloud-Monitor`.
2. Select **RASD Ministry official + RSS — manual strict Word owner review (NO Gmail)**.
3. Click **Run workflow**, select `main` and `yesterday` (preferred full calendar day). It is restricted to repository actor `Hatem1984`.
4. After the run, download the artifact named `rasd-g43-owner-encrypted-<run_id>`. It contains `rasd-g43-owner-encrypted.json` only; retention is **1 day**.
5. On the **owner's own Windows computer** with Python and the original RSA private key paired to the existing public file, use the repository's `gate43_owner_encrypted_review.py` script:

```powershell
python -m pip install "cryptography>=42,<50"
python gate43_owner_encrypted_review.py --decrypt --payload "C:\\RASD-Review\\rasd-g43-owner-encrypted.json" --private-key "C:\\PRIVATE-KEY-LOCATION\\your-original-private-key.pem" --destination "C:\\RASD-Review\\decrypted"
```

**Replace placeholders with real local paths.** Never upload or paste the RSA private key, email passwords or recovery keys to ChatGPT, GitHub Actions or the public repo. If the original private key is unavailable, do **NOT** bypass encryption to share the report.

6. Review every page of the decrypted **actual original report Word**, checking Arabic RTL shaping, the title, source/date, one genuine screenshot for each article, readability, page breaks/clipping, and absence of unsupported extra articles. Mark `human_visual_review` separately; the encrypted audit purposely marks it `false` until a real reviewer has examined it.

The encryption package is not itself proof the whole project is production-ready. The original email delivery, storage and scheduling approval gates remain closed.

## Required completion evidence — Stage 2 remains OPEN until fulfilled

- At least two distinct healthy **real Cairo full-day** source windows, with all three sources available and one original screenshot per included article, proven as complete Word.
- A decrypted genuine Word individually reviewed on every rendered page by owner or authorized reviewer; synthetic and machine raster checks are NOT a substitute.
- Original source official NewsList and exact four Ministry terms are used by the report; no broadened economic categories or omitted unavailable feed, no arbitrary story quotas.
- Only then issue Stage 2 100% acceptance, and move to privately approved storage (Stage 3), then real Gmail (Stage 4). Do not enable either from this manual workflow.

## Evidence and CI interpretation

On 18 October 2026, real hosted two-day reports were held when the Al Masry Al Youm RSS was unavailable in some runs. That is a valid fail-closed result, **not** an approved report. Earlier 17 October combined official/Hapi Word proof with two real screenshots passed in isolated Gate40/Gate41 runs. This Gate43 closes the *manual operational integration* subgate but does **not** assert multi-day visual or source reliability acceptance.
