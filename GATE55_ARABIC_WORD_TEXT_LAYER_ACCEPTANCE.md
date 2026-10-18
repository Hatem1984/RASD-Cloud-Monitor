# Gate55 — correct Arabic presentation-form comparison in private Word QA

**Date:** 18 October 2026. Ministry of Planning-only RASD V1 with four exact saved terms and three qualified original publisher sources. No source or keyword change.

## Real original-source finding

[Gate54 real full-day Word QA #39132446099](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39132446099) found a full-day 17 October 2026 report with **ALL THREE originals HEALTHY**: official Ministry archive **20 URLs in two pages, one same-day article**; Hapi RSS **10 links**; Al Masry Al Youm approved RSS **50 links**, strict valid XML. `failures={}`, genuine Ministry original-page image **1/1 verified**, `word_created=true`, `word_images_verified=true`. But private LibreOffice PDF text extraction failed `qa_rendered_original_headline_missing`, so the gated runner correctly aborted BEFORE packaging owner ciphertext and NEVER published incomplete Word. A source or JPEG integrity issue was NOT proven in this run; rendered Arabic headline text-layer mismatch remains a distinct hold.

## Constrained QA change

`word_render_audit._arabic_headline_tokens` now applies Unicode **NFKC only to the extracted-text comparison**, followed by typographic Arabic marks/tatweel normalization and common Alef variants. NFKC expands Arabic compatibility presentation glyphs and lam–alef ligatures into their underlying spellings. The existing mechanism still requires article-specific original Arabic headline tokens on the ACTUAL PDF text layer and still blocks a missing or substituted original headline; no OCR, raw publisher headline logs, missing-title fallback or numerical check removal.

**Never modified by this gate:** original publisher title, article links, original publication timestamps, Word document text, publisher JPEG bytes, ordered SHA-256 picture relationship, RSS feed endpoints, 15-item cap, encrypted 1600px page review or source eligibility. The private render PDF remains ephemeral and is NOT a user deliverable.

## Acceptance distinctions

- Synthetic unit tests verify presentation-form/ligature equivalence and rejection when the actual article heading is missing. They do NOT prove the cause of the actual Gate54 Word failure by themselves.
- Dedicated branch-only original-publisher Word run `.github/workflows/gate55-real-word-arabic-layout.yml` can produce a single owner-encrypted private Word+rendered-pages package ONLY if all three approved sources are fully healthy and every original image and rendered title passes. It can instead correctly return `HOLD`.
- **Human visual inspection of all actual Word pages is not performed by unit tests.** Stage2 Issue #42 remains OPEN until genuine owner/authorized page-by-page visual review and a *second distinct full Cairo day* both pass. Gmail, R2, cron, account credentials and plaintext published media are prohibited until their later gates.
