# RASD — Gate 38: official Ministry original-source qualification

**Date:** 18 October 2026 • **Engineering subgate:** Original-article screenshot + Word evidence VERIFIED.  
**Full Stage 1 discovery:** **HOLD** — official original-publisher index has NOT exposed discoverable article links in the tested hosted browser session.

## Actual original-publisher evidence

An independently verified public Ministry of Planning URL:
- `https://mped.gov.eg/singlenews?id=7269&lang=ar`
- Original Ministry page heading mentions **وزير التخطيط** and an economic transformation program.
- The **original publisher page** explicitly prints `17 أكتوبر 2026`. The site does not publish an exact time in this proof, so **no hour was invented**.
- Browser QA on the hosted GitHub runner opened this exact original URL, verified page host/identity, Ministry saved-term relevance, exact Arabic publication calendar date, and page content.
- First bounded viewport screenshot was insufficient and rejected; a genuine **full-page screenshot of the same original rendered article** passed existing JPEG size/visual-quality tests. Word was generated **in ephemeral runner storage** and its DOCX drawing image SHA-256 verified against the captured JPEG. NO mock image was substituted for live proof.

**Final tested code version:** [CI run 39111006045](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39111006045).

### Crucial discovery limit

The same live browser examined the official Ministry press release index `https://mped.gov.eg/News?id=57&lang=ar`, but found **0 valid article anchors**. Independent read-only fetches of `/News?lang=ar`, `/News/index?lang=ar` and `www` returned `لا يوجد نتائج للبحث`. Thus **the one known public article is NOT counted as automatic index discovery**. This module refuses `READY_SOURCE_QA_ONLY` unless BOTH the index yields original article links and its independently known sample page passes screenshot-into-Word evidence. Live result: `HOLD`.

The approved production Hapi/Al Masry RSS feed profiles and all four Ministry phrases remain UNCHANGED. New source is **not** registered or automatically triggered; there is no Google search API, scrape bypass, ID enumeration or third-party RSS presented as original evidence.

## Implemented

- `official_ministry_source.py`: separate branch-gated, read-only Playwright source QA. Exact `mped.gov.eg` resource allowlist and `/singlenews?id=<positive-id>&lang=ar` canonical URL constraints. Reject extra query parameters, foreign hosts, URL username/password, invalid ports, malformed IDs and redirects to other source identities.
- Parse original index DOM anchors only — no guessed numeric IDs. Limit input HTML and 35 unique article links per probe. **No** claim of completeness from an empty page.
- Independently check the original article heading, saved-keyword relevance, Arabic publisher publication day *adjacent to heading*, content availability, correct tested day, and genuine browser-rendered JPEG quality. Date-only sources **do not acquire a synthetic timestamp**.
- Reuse existing `render_docx` and `word_images_match_capture_digests` for strict binary media binding. Temporary Word/image are removed after test, not published to public Actions artifacts.
- `tests/test_gate38_official_ministry_source.py`: no-network synthetic regression fixtures for URL allowlists, original index anchors, duplicate/cross-domain rejection, Arabic date validation, fail-closed on wrong date/relevance/source HTTP status, Word/JPEG SHA checks.
- Existing `main`-only production workflows, Gmail, private R2, scheduled delivery, 15-story production cap, source configs remain UNCHANGED.

## Stage 1 gate (still OPEN)

- [x] Verify a real official Ministry article dated 17 October with its original browser screenshot and Word per-article SHA-256 in ephemeral hosted CI.
- [x] Strict, bounded official-source prototype and adversarial offline tests.
- [ ] Discover current fresh article links repeatedly from an original Ministry-operated accessible listing, archive or documented endpoint, with pagination health and exact source dates. An empty official index is NOT coverage.
- [ ] Qualify source for production only after list + original-page live acceptance and article deduplication against original publisher news.
- [ ] Demonstrate sustainable full-source daily proof with all selected original pages in final Word; if missing/blocked, preserve HOLD.
- [ ] Keep all four saved Ministry planning phrases and official publisher list reviewed; do not broaden the mission to generic economic news.

**Product impact:** Stage 1 has materially advanced but remains below 100%. Stage 2 final Word acceptance, Stage 3 private store, Stage 4 Gmail, Stage 5 scheduler, Stage 6 multiday acceptance, Stage 7 clients remain in that order. No credentials, subscription, live mail, scheduler or public screenshot artifact were enabled.
