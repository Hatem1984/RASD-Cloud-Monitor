# RASD Gate49 — private Arabic Word rendered-legibility acceptance

**Date:** 18 October 2026 (Africa/Cairo). **Policy:** Egyptian Ministry of Planning V1 with the existing EXACT four saved phrases and approved Hapi/Al Masry Al Youm/Ministry original-page sources. No new source or general economic keyword.

## Why this Gate exists

A valid publisher screenshot may be a very tall full-page JPEG. When squeezed to a 6.2-inch Word page height while preserving the image aspect ratio, a 1200×5100 source image renders only ~1.46 inches wide. This has a valid JPEG SHA and can pass blank-page checks, but the original article screenshot is far too narrow to be read conveniently. The previous `word_render_audit.py` allowed widths as small as 0.6 inches. That was not an adequate **visual legibility gate**.

## New automatically enforceable layout conditions

1. The exact original JPEG file stays unchanged, with the established SHA-256 binding in every selected article. No cropping, image regeneration, substitution or fake zoom.
2. The placed screenshot must be at least **3.0 inches wide** in the Word and cannot exceed 5.6 inches width or 6.2 inches height. Any original image too tall to fit legibly → `HOLD`, NOT a silently shrunk screenshot or incomplete Word.
3. The REAL private LibreOffice export of a candidate `DOCX` is inspected with Poppler's `pdftotext -layout`, not OCR. Each article's original Arabic heading must survive rendering in the extractable text layer, checked by its longest Arabic headline words. Failing/missing text layer or an article heading → `HOLD`. The PDF, page rasters and Word are never uploaded in plaintext.
4. Existing PDF page-to-PNG blank/missing page checks remain active. `human_visual_review=false` stays explicit because neither text-layer tests nor geometric width prove all glyphs, line breaks, image clarity, RTL alignment, or non-clipping on every page.
5. Owner private decryption key remains local. The previously approved 1-day RSA-OAEP/AES-GCM ciphertext route remains exactly as designed. No Gmail, R2, cron, recipient or source keyword changes.

## Real CI evidence (synthetic pictures, not publisher evidence)

- [Branch offline and source test CI 39124342639](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39124342639): two jobs pass, **252 unit tests**, including original JPEG digest unchanged and image readability regression.
- [Private actual LibreOffice rendering 39124342680](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39124342680): source-independent **synthetic Arabic Word with two images** rendered privately into **two pages**. Two Arabic headlines survived PDF text extraction; screenshot widths met the 3.0-inch minimum, no blank pages. A deliberately tall 1200×5100 synthetic publisher-like image correctly returned `qa_publisher_picture_too_narrow_or_outside_page` (HOLD).
- No real original private Word was decrypted or inspected by a human in this gate. The genuine October 17 Word is in the prior owner encrypted artifact [39123380215](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39123380215), **NOT** publicly accessible as plaintext and **NOT** retroactively certified by the new stricter renderer check.

## Stage 2 closure requirements STILL OPEN

- [ ] Review ALL original Word pages from the encrypted owner artifact on the owner's device, after using the matching LOCAL private key. Verify Arabic RTL, readable original screenshot and headlines, original publication date and source identity and page breaks. Do not paste private keys/tokens into chat or GitHub.
- [ ] A second **distinct, fully completed Cairo calendar day** must pass ALL three original publishers, genuine one-image-per-article Word SHA, new legibility/text-layer automatic checks and encrypted private review. On Sunday 18 October 2026, the new day's completed window is NOT yet available; do not substitute today's PARTIAL window or claim historical rolling RSS is exhaustive.
- [ ] Owner/authorized human signoff on Stage 2. Until then Issue #42 remains OPEN and Stage2 percentage is ONLY an engineering estimate, never 100%.

**No email send, scheduled news run, paid storage or public private media artifacts.** This branch implements offline and private-render QA protection, not unattended daily delivery activation.
