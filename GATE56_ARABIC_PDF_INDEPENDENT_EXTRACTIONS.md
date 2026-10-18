# Gate56 — two independent Poppler PDF text extraction modes for real Arabic Word QA

Date: 18 October 2026, Cairo. RASD V1 Ministry of Planning only. Exact original four saved Ministry phrases and existing 3 approved original sources. No change to sources.json, original publisher article link/date/title or screenshot SHA.

## Verified real-world blocker

[Gate54 real Word #39132446099](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39132446099) and [Gate55 real Word #39133203610](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39133203610) **both independently had 3/3 original source health** and verified real Word 1/1 genuine publisher screenshot. Government official original archive had 20 links across two pages, one matching original publication date Oct17; Hapi 10 links; Al Masry 50 original RSS links. Word was constructed and original-page image SHA validated, but both runs rejected delivery at `qa_rendered_original_headline_missing` from Poppler's `pdftotext -layout` even after NFKC Arabic presentation-form normalization.

**Interpretation:** This is NOT a successful Word release. The earlier assumption that Unicode presentation shapes alone explain the layout-layer mismatch was not confirmed by real CI. Automated Word PDF-text acceptance remains an independent fail-closed gate.

## Gate56 narrowly tests a second representation of the same private PDF

After a `-layout` missing-title error only, run `pdftotext -raw` on the SAME LibreOffice-rendered PDF (never any third-party file or OCR). Require all original article heading tokens to survive in ONE complete extraction mode, either `layout` or `raw`. NEVER combine a few headline words from each view to pass a full heading, never alter original Word/JPEG/source, never ignore all missing title checks. Missing Arabic text layer, wrong article count, missing or swapped titles and broken screenshots still remain HOLD.

The returned audit identifies only `arabic_text_extraction_mode` (`layout` or `raw`), not any source article text. Render images remain private to the owner RSA/AES encrypted bundle and page-by-page HUMAN review remains mandatory.

## Acceptance boundaries

- Branch-only real Word run `gate56-real-word-title-dual-extract.yml` either returns genuinely valid 3/3 original source + strict PDF extraction + encrypted-only owner Word with 1600px private review pages, or declines without a final Word. It is NOT human visual review.
- Stage2 Issue #42 cannot close at 100% without owner inspecting each real decrypted Word page AND second distinct fully completed Cairo reporting date. October18 incomplete until Cairo Oct19. No Gmail, R2, cron or public Word/JPEG/PNG/PDF.
